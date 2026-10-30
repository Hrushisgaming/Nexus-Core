"""Gemini Live voice runtime for Nexus Core.

The runtime class is isolated from the application entry point. A temporary
namespace bridge keeps legacy integrations available while remaining methods
are progressively extracted into focused services.
"""
import main as _main
globals().update({name: value for name, value in vars(_main).items() if not name.startswith("__")})

class BrahmaLive:

    def __init__(self, ui: BrahmaUI, dashboard=None, dashboard_started: bool = False, enable_dashboard: bool = True):
        self.ui             = ui
        self._smart_home    = SmartHomeService()
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._startup_briefing_started = False
        self._loop          = None
        self._is_speaking   = False
        self._server_turn_active = False
        self._discard_server_audio = False
        self._spoke_start_time = 0.0
        self._last_spoke_time = 0.0
        self._speaking_lock = threading.Lock()
        self._use_openrouter_first = False
        self._pending_attention: dict | None = None
        self._pending_reply_event: dict | None = None
        self._reply_mode = False
        self._attention_lock = threading.Lock()
        self._attention_monitor = AttentionMonitor(on_event=self._on_external_notification)
        try:
            set_speech_sink(self.speak)
        except Exception:
            pass
            
        try:
            from actions.background_monitor import set_monitor_speech_sink
            set_monitor_speech_sink(self.speak)
        except Exception as e:
            print(f"[Main] Failed to init background monitor: {e}")
        self._meeting_lock = threading.Lock()
        self._meeting_active = False
        self._meeting_event: dict | None = None
        self._meeting_assistant = MeetingAssistant(
            on_update=self._on_meeting_update,
            on_state=self._on_meeting_state,
        )
        self._phone_active = False
        self._dashboard = dashboard if dashboard is not None else (DashboardServer() if (enable_dashboard and DashboardServer is not None) else None)
        self._dashboard_started = bool(dashboard_started and self._dashboard is not None)
        self.ui.on_text_command = self._on_text_command
        self.ui.on_attention_action = self._on_attention_action
        self.ui.on_remote_clicked = self._make_remote_key
        self._echo = EchoGuard()
        self._resume_handle = None
        self._ptt = None
        self._ptt_held = False
        try:
            self._ptt_enabled = config_manager.get_push_to_talk_enabled()
            if self._ptt_enabled:
                self.set_push_to_talk(True)
        except Exception:
            self._ptt_enabled = False

        try:
            audio_devices.configure(SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE)
            audio_devices.prefetch()
        except Exception:
            pass
        self._last_activity = time.monotonic()
        self._idle_prompts = [
            "Hey, you there?",
            "Yo, get alive.",
            "How may I help, bro?",
            "Need anything?",
            "I'm here if you want me.",
        ]
        try:
            from core.live_voice_engine import LiveVoiceEngine
            _lve = LiveVoiceEngine.get_instance()
            self._lve = _lve
            _lve.on_user_transcript = lambda txt, interim: self.ui.set_live_subtitles("YOU", txt, interim)
            _lve.on_ai_transcript = lambda txt, interim: self.ui.set_live_subtitles("NEXUS", txt, interim)
        except Exception:
            pass

        self._idle_speech_thread = threading.Thread(target=self._idle_speech_loop, daemon=True)
        self._idle_speech_thread.start()

    def set_push_to_talk(self, enabled: bool) -> str:
        self._ptt_enabled = bool(enabled)
        self._ptt_held = False
        if not enabled:
            if self._ptt is not None:
                self._ptt.stop()
                self._ptt = None
            return "off"
        if self._ptt is None:
            self._ptt = PushToTalk(self._on_ptt)
        scope = self._ptt.start()
        try:
            self.ui.write_log(
                f"SYS: Push-to-talk on — hold {self._ptt.label}"
                + ("." if scope == "global" else " (works while window focused).")
            )
        except Exception:
            pass
        return scope

    def _on_ptt(self, held: bool) -> None:
        self._ptt_held = held

    def _reset_idle_activity(self):
        self._last_activity = time.monotonic()

    def _should_announce_idle(self) -> bool:
        if self.ui.muted:
            return False
        if self._is_speaking:
            return False
        if self._meeting_active:
            return False
        if self._pending_attention:
            return False
        if time.monotonic() - self._last_activity < 240:
            return False
        return True

    def _idle_speech_loop(self):
        try:
            from actions.proactive import ProactiveEngine
            engine = ProactiveEngine(min_silence_secs=300, check_cooldown=600)  # Shorter defaults for testing
        except ImportError:
            engine = None

        while True:
            time.sleep(60.0)
            if not engine:
                continue
            
            try:
                if self.ui.muted or self._is_speaking or self._meeting_active or self._pending_attention:
                    continue
                
                # Check if it should trigger using the engine's time monotonic logic
                if engine.should_trigger(self._last_activity):
                    engine.mark_triggered()
                    prompt = engine.build_prompt(memory={})
                    
                    if self.session and self._loop:
                        import asyncio
                        async def _send():
                            try:
                                content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
                                await self.session.send_client_content(turns=[content], turn_complete=True)
                            except Exception as e:
                                print(f"[Proactive] Error: {e}")
                        asyncio.run_coroutine_threadsafe(_send(), self._loop)
                        self._reset_idle_activity()
                    
            except Exception as e:
                print(f"[Proactive] Error: {e}")

    def _make_remote_key(self):
        if self._dashboard is None:
            self.ui.write_log("ERR: Mobile Connect unavailable. Install fastapi, uvicorn, cryptography, and qrcode[pil].")
            return None
        key = self._dashboard.new_key()
        url = self._dashboard.get_url()
        manual = self._dashboard.get_manual_url()
        return url, key, f"{url}/auto-login?key={key}", manual

    def _on_phone_connected(self):
        try:
            self.ui.notify_phone_connected()
        except Exception:
            pass

    def _on_text_command(self, text: str, source: str = "local"):
        self._reset_idle_activity()
        text = (text or "").strip()
        if not text:
            return
        if len(text) > 4:
            threading.Thread(
                target=_update_memory_async,
                args=(text, ""),
                daemon=True
            ).start()
        self.ui.set_state("THINKING")
        try:
            stop_native_speech()
        except Exception:
            pass

        # Fast emergency stop check for active StudyGuard session
        lower_fast = text.lower().strip()
        study_stop_words = {
            "stop", "stop it", "cancel", "halt", "end", "quit", "abort",
            "stop study", "stop studying", "cancel study", "end study", "quit study",
            "stop session", "end session", "cancel session", "stop study session", "end study session"
        }
        if lower_fast in study_stop_words or any(lower_fast.startswith(p + " ") for p in ("stop study", "end study", "cancel study", "stop session")):
            try:
                from core.study_guard import get_study_guard_manager
                sg = get_study_guard_manager()
                if sg.is_active:
                    res = sg.stop_session()
                    stats = res.get("stats", {})
                    card_path = res.get("card_path")
                    summary = res.get("summary", "")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Session Stopped", output=summary, percent=100)
                    if hasattr(self.ui, "show_hud_deliverable"):
                        self.ui.show_hud_deliverable(
                            title=f"Study: {stats.get('subject', 'Sprint')}",
                            summary=f"Focus Efficiency: {stats.get('focus_score')}%\nTotal Time: {int(stats.get('total_seconds', 0) // 60)}m",
                            bullets=[
                                f"Focus Score: {stats.get('focus_score')}%",
                                f"Focus Time: {int(stats.get('active_focus_seconds', 0) // 60)} minutes",
                                f"Sleep Alerts: {stats.get('sleep_alerts', 0)}",
                                f"Phone Distractions: {stats.get('phone_alerts', 0)}",
                            ],
                            file_path=card_path,
                            kind="study_guard"
                        )
                    self.speak("Study session stopped, sir.")
                    return
            except Exception as e_sg_stop:
                self.ui.write_log(f"ERR: StudyGuard stop failed: {e_sg_stop}")

        # allow plugins to handle the incoming text command first
        try:
            pm = getattr(self, "plugin_manager", None)
            if pm is not None:
                handled = pm.dispatch("on_text_command", text, source)
                if handled:
                    return
        except Exception:
            pass
        if self._reply_mode:
            if self._handle_pending_reply(text):
                return
            # Still in reply mode but no pending reply event means reset and continue
            self._reply_mode = False

        if getattr(self, "_ig_reply_mode", False):
            if self._handle_ig_reply_flow(text):
                return

        if getattr(self, "_email_mode", False):
            if self._handle_email_flow(text):
                return

        # Direct verbal toggle for Air-Gapped Offline Mode
        lower = text.lower().strip()
        if any(p in lower for p in ("switch to offline mode", "go offline", "turn on offline mode", "enable offline mode", "air gap mode")):
            config_manager.set_setting("offline_mode_enabled", True)
            config_manager.set_setting("default_ai_provider", "Local")
            self.ui.write_log("🔒 SYSTEM: Air-Gapped Offline Mode ENGAGED. All operations running 100% locally.")
            self.speak("Offline mode engaged, sir. Running 100 percent locally on your machine.", proactive=True)
            return

        if any(p in lower for p in ("switch to online mode", "go online", "turn off offline mode", "disable offline mode")):
            config_manager.set_setting("offline_mode_enabled", False)
            config_manager.set_setting("default_ai_provider", "Google Gemini")
            self.ui.write_log("🌐 SYSTEM: Offline Mode DISENGAGED. Cloud connectivity restored.")
            self.speak("Online mode restored, sir. Cloud connectivity is active.", proactive=True)
            return

        # Check for email command initiation
        lower = text.lower()
        skill_goal = _extract_skill_creation_goal(text)
        if skill_goal is not None:
            if not skill_goal:
                prompt = "What should the new skill or feature do?"
                self.ui.write_log(f"Nexus Core: {prompt}")
                self.speak(prompt)
                return

            try:
                self.ui.begin_task_workspace(
                    text,
                    ["Generate the requested feature", "Validate it in the skill sandbox", "Register it for future use"],
                    source=source or "local",
                )
            except Exception:
                pass

            self.speak("Starting feature creation now.")
            threading.Thread(
                target=self._forge_skill,
                args=(skill_goal,),
                daemon=True,
                name="skill-forge",
            ).start()
            return

        if lower.startswith("email ") or lower.startswith("mail ") or "send email" in lower or "write email" in lower or "compose email" in lower:
            # Extract recipient
            rem = text
            for prefix in ("send email", "send an email", "write email", "write an email", "compose email", "compose an email", "email", "mail"):
                if rem.lower().strip().startswith(prefix):
                    rem = rem.strip()[len(prefix):].strip()
                    break
            
            # Remove leading "to " if present
            if rem.lower().startswith("to "):
                rem = rem[3:].strip()
                
            recipient = rem.strip()
            self._email_mode = True
            self._email_recipient = recipient
            
            try:
                self.ui.begin_task_workspace(
                    text,
                    [
                        "Identify the recipient",
                        "Select email application",
                        "Collect message content",
                        "Open application & compose",
                    ],
                    source=source or "local",
                )
            except Exception:
                pass
                
            if not recipient:
                self._email_step = 0
                prompt = "Who would you like to send the email to?"
                self.ui.write_log(f"Nexus Core: {prompt}")
                self.speak(prompt)
                try:
                    self.ui.update_task_workspace(
                        status="Identifying recipient",
                        output="Asking for email recipient...",
                        percent=10,
                    )
                except Exception:
                    pass
            else:
                self._email_step = 1
                prompt = "Which email app would you like to use? (Gmail, default mail app, etc.)"
                self.ui.write_log(f"Nexus Core: {prompt}")
                self.speak(prompt)
                try:
                    self.ui.update_task_workspace(
                        status="Selecting email app",
                        output=f"Recipient identified: {recipient}. Asking for email application...",
                        percent=25,
                    )
                except Exception:
                    pass
            return

        if _looks_like_daily_briefing_request(text):
            try:
                self.ui.begin_task_workspace(
                    text,
                    ["Collecting weather, schedule, inbox, and headlines", "Delivering your briefing"],
                    source=source or "local",
                )
            except Exception:
                pass
            self.speak("Preparing your daily briefing.")

            def _run_daily_briefing():
                try:
                    from actions.daily_briefing import daily_briefing
                    daily_briefing(parameters={"category": "all"}, player=self.ui, speak=self.speak)
                except Exception as exc:
                    message = f"Daily briefing failed: {exc}"
                    try:
                        self.ui.write_log(f"ERR: {message}")
                    except Exception:
                        pass
                    self.speak(message)

            threading.Thread(
                target=_run_daily_briefing,
                daemon=True,
                name="daily-briefing",
            ).start()
            return

        try:
            from smart_home.smart_device_manager import SmartDeviceManager
            sd_mgr = SmartDeviceManager()
            devices = self._smart_home.list_devices()
            routed_text_home = sd_mgr.route_command(text, devices)
            if routed_text_home != text:
                print(f"[NEXUS CORE] Redirection: '{text}' -> '{routed_text_home}'")
                text = routed_text_home
        except Exception as e:
            print(f"[NEXUS CORE] Redirection error: {e}")

        # =========================================================================
        # 3-TIER INTELLIGENT INTENT DISPATCHER
        # Tier 1: Instant Local Reflex (< 2ms)
        # Tier 2: Learned Phrase Cache (< 1ms)
        # Tier 3: Fast Semantic AI (~200ms)
        # =========================================================================
        try:
            from core.intent_dispatcher import get_intent_dispatcher
            dispatcher = get_intent_dispatcher()

            connected_devices = []
            try:
                from actions.nexus_connect import connect_list_devices
                dev_res = json.loads(connect_list_devices(parameters={}, player=self.ui))
                connected_devices = dev_res.get("devices", [])
            except Exception:
                connected_devices = []

            active_win = ""
            try:
                if hasattr(self.ui, "get_active_window_title"):
                    active_win = self.ui.get_active_window_title()
            except Exception:
                pass

            # If Gemini Live duplex session is active, bypass slow Tier 3 REST classification for 0ms local reflex
            live_active = bool(self.session and self._loop and getattr(self, "_loop", None).is_running())
            intent_res = dispatcher.resolve(
                text,
                connected_devices=connected_devices,
                active_window=active_win,
                enable_ai_tier=(source != "instagram" and not live_active)
            )

            if intent_res.intent == "media_control":
                def _run_media_control():
                    try:
                        from actions.media_keys import volume_up, volume_down, volume_mute, volume_set, media_play_pause, media_next, media_previous
                    except Exception:
                        pass
                    if intent_res.action == "volume_up":
                        volume_up()
                    elif intent_res.action == "volume_down":
                        volume_down()
                    elif intent_res.action == "volume_mute":
                        volume_mute()
                    elif intent_res.action == "volume_set":
                        val = int(intent_res.parameters.get("value", 50))
                        volume_set(val)
                    elif intent_res.action in {"media_pause", "media_play"}:
                        media_play_pause()
                    elif intent_res.action == "media_next":
                        media_next()
                    elif intent_res.action == "media_previous":
                        media_previous()
                    if intent_res.voice_ack:
                        self.speak(intent_res.voice_ack)
                threading.Thread(target=_run_media_control, daemon=True).start()
                return

            if intent_res.intent == "meeting_mode":
                if intent_res.action == "start":
                    self._start_meeting_mode("Meeting mode activated.")
                else:
                    self._stop_meeting_mode("Meeting mode closed.")
                return

            if intent_res.intent == "open_app":
                from actions.open_app import open_app
                app_name = intent_res.parameters.get("app_name", "")
                if app_name:
                    def _run_open_local():
                        open_app({"app_name": app_name}, player=self.ui)
                        self.speak(intent_res.voice_ack or f"Opening {app_name}, sir.")
                    threading.Thread(target=_run_open_local, daemon=True).start()
                    return

            if intent_res.intent == "mobile_connect" and source != "instagram":
                if self._handle_nexus_connect_command(text, source=source or "local", parsed_intent=intent_res):
                    return

            if intent_res.intent == "vision":
                vision_angle = intent_res.parameters.get("angle", "camera" if "cam" in intent_res.action else "screen")
                workspace_title = "Webcam Inspection" if vision_angle == "camera" else "Screen Analysis"
                status_text = "Checking camera..." if vision_angle == "camera" else "Scanning screen..."
                output_text = "Nexus Core is inspecting your camera..." if vision_angle == "camera" else "Nexus Core is inspecting your screen..."
                
                try:
                    self.ui.update_task_workspace(
                        title=workspace_title,
                        command=text,
                        plan=["Capture visual frame", "Analyze with vision AI", "Report observations"],
                        status=status_text,
                        output=output_text,
                        percent=40,
                        source=source or "local",
                    )
                except Exception:
                    pass

                img_bytes = None
                if vision_angle == "screen" and hasattr(self.ui, "capture_screen_bytes"):
                    img_bytes = self.ui.capture_screen_bytes()

                def _run_vision_process():
                    success = screen_process(
                        parameters={"angle": vision_angle, "text": text},
                        response=None,
                        player=self.ui,
                        session_memory=None,
                        image_bytes=img_bytes,
                    )
                    if not success:
                        try:
                            self.ui.update_task_workspace(
                                status=f"{workspace_title} failed",
                                output="Visual perception could not complete. Check your camera or screen permissions.",
                                percent=0,
                            )
                        except Exception:
                            pass
            if intent_res.intent == "shopping" and intent_res.action in ("open_item", "open_link", "buy_now"):
                from core.shopping_agent import get_shopping_agent
                agent = get_shopping_agent()
                target_plat = intent_res.parameters.get("platform")
                target_mode = intent_res.parameters.get("mode", "pc")
                res = agent.open_last_item(platform=target_plat, mode=target_mode)
                if res.get("success"):
                    prod_title = res.get("item", {}).get("title", "product")[:40]
                    plat_name = str(res.get("platform") or "store").capitalize()
                    dest = "on your phone" if target_mode == "phone" else "in your browser"
                    self.speak(f"Opened the {plat_name} page for {prod_title} {dest}, sir.")
                else:
                    self.speak(res.get("error") or "No recent shopping item found to open, sir.")
                return

            if intent_res.intent == "shopping":
                query_prod = str(intent_res.parameters.get("query") or text)
                target_platform = str(intent_res.parameters.get("platform") or "both").lower()
                self.speak(intent_res.voice_ack or f"Scanning e-commerce deals for {query_prod}, sir.")
                if hasattr(self.ui, "begin_task_workspace"):
                    self.ui.begin_task_workspace(
                        f"Shopping Agent: {query_prod}",
                        [
                            "Search Amazon India & Flipkart",
                            "Cross-compare prices & delivery speeds",
                            "Extract customer reviews (Rufus-style)",
                            "Launch top item link in browser",
                            "Generate interactive HUD deliverable",
                        ],
                        source=source or "local"
                    )

                def _run_shopping():
                    try:
                        from core.shopping_agent import get_shopping_agent
                        agent = get_shopping_agent()
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Scanning stores...", percent=35)

                        if target_platform == "amazon":
                            amz = agent.search_amazon_playwright(query_prod, limit=4)
                            flp = []
                        elif target_platform == "flipkart":
                            amz = []
                            flp = agent.search_flipkart_playwright(query_prod, limit=4)
                        else:
                            both = agent.search_both_parallel(query_prod, limit_per_store=3)
                            amz = both.get("amazon", [])
                            flp = both.get("flipkart", [])

                        if not amz and not flp:
                            msg = f"I couldn't find live listings for '{query_prod}' on Amazon or Flipkart right now, sir."
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(status="No Products Found", output=msg, percent=0)
                            self.speak(msg)
                            return

                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Synthesizing deals...", percent=75)

                        synthesis = agent.synthesize_rufus_recommendation(query_prod, amz, flp)
                        card_html = agent.generate_hud_shopping_card(query_prod, synthesis, amz, flp)

                        best = synthesis.get("best_overall")
                        verdict = synthesis.get("verdict", "")
                        voice_msg = synthesis.get("voice_summary", "")

                        # Automatically launch top recommended product link in default browser!
                        if best and best.url:
                            agent.execute_cart_or_buy(best.url, platform=best.platform, mode="pc")

                        if hasattr(self.ui, "update_task_workspace"):
                            out_summary = f"Top Pick: {best.title if best else 'Recommended'}\nPrice: ₹{best.price:,.0f} ({best.platform.capitalize() if best else ''})\n\n{verdict}"
                            self.ui.update_task_workspace(status="Comparison Complete & Opened in Browser", output=out_summary, percent=100)

                        if hasattr(self.ui, "show_hud_deliverable"):
                            self.ui.show_hud_deliverable(
                                title=f"Shopping: {query_prod[:28]}",
                                summary=verdict,
                                bullets=[
                                    f"Top Pick: {best.title[:45]} (₹{best.price:,.0f})" if best else "",
                                    f"Platform: {best.platform.capitalize() if best else ''}",
                                    f"Deal: {best.badge if best and best.badge else 'In Stock'}",
                                    "Status: Opened in browser",
                                ],
                                file_path=card_html,
                                kind="shopping"
                            )

                        if voice_msg:
                            self.speak(voice_msg + f" I have opened the {best.platform.capitalize()} listing in your browser, sir.")
                        elif best:
                            self.speak(f"The best option is {best.title[:45]} on {best.platform.capitalize()} for ₹{best.price:,.0f}. I've opened the link in your browser and loaded the comparison card on your HUD, sir.")

                    except Exception as exc:
                        self.ui.write_log(f"ERR: Shopping agent failed: {exc}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Search Failed", output=str(exc), percent=0)
                        self.speak("I encountered an issue searching for that item, sir. Please check the network connection.")

            if intent_res.intent == "flowstate":
                fs_action = str(intent_res.action or "snapshot").lower()
                ws_name = str(intent_res.parameters.get("name") or "Main Workspace")
                self.speak(intent_res.voice_ack or f"Processing FlowState workspace '{ws_name}'...")

                def _run_flowstate():
                    try:
                        from core.flowstate import get_flowstate_manager
                        manager = get_flowstate_manager()

                        if fs_action in ("snapshot", "save", "create"):
                            if hasattr(self.ui, "begin_task_workspace"):
                                self.ui.begin_task_workspace(
                                    f"FlowState: Snapshot '{ws_name}'",
                                    ["Enumerate running apps", "Extract Chrome & Edge tabs", "Record VS Code workspaces", "Save to persistent storage"],
                                    source=source or "local"
                                )
                            res = manager.snapshot_workspace(ws_name)
                            apps_count = res.get("apps_count", 0)
                            tabs_count = res.get("chrome_tabs_count", 0) + res.get("edge_tabs_count", 0)
                            workspaces = res.get("vscode_workspaces", [])
                            summary = f"Saved '{ws_name}'\n• {apps_count} desktop applications\n• {tabs_count} active browser tabs\n• {len(workspaces)} code projects\n\nSurvives reboots permanently."

                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(status="Workspace Snapshotted", output=summary, percent=100)

                            if hasattr(self.ui, "show_hud_deliverable"):
                                self.ui.show_hud_deliverable(
                                    title=f"FlowState: {ws_name}",
                                    summary=f"Snapshot created at {res.get('created_str')}",
                                    bullets=[
                                        f"Apps: {apps_count} running",
                                        f"Browser Tabs: {tabs_count} active",
                                        f"Projects: {len(workspaces)} folders",
                                        "Status: Saved to persistent disk",
                                    ],
                                    kind="flowstate"
                                )
                            self.speak(f"Workspace '{ws_name}' has been snapshotted with {apps_count} apps and {tabs_count} browser tabs, sir. You can reboot anytime.")

                        elif fs_action in ("restore", "load", "switch"):
                            if hasattr(self.ui, "begin_task_workspace"):
                                self.ui.begin_task_workspace(
                                    f"FlowState: Restore '{ws_name}'",
                                    ["Load snapshot from disk", "Relaunch Chrome & Edge tabs", "Relaunch VS Code projects", "Relaunch desktop applications"],
                                    source=source or "local"
                                )
                            res = manager.restore_workspace(ws_name)
                            if res.get("success"):
                                items = res.get("restored_items", [])
                                summary = f"Restored '{ws_name}'\n" + "\n".join([f"• {it}" for it in items])
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="Workspace Restored", output=summary, percent=100)
                                self.speak(f"Restored workspace '{ws_name}' with {len(items)} applications and tabs, sir.")
                            else:
                                err = res.get("error", "Workspace not found.")
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="Restore Failed", output=err, percent=0)
                                self.speak(f"Could not restore workspace '{ws_name}': {err}")

                        elif fs_action in ("list", "show"):
                            workspaces = manager.list_workspaces()
                            if workspaces:
                                names = [w["name"] for w in workspaces]
                                summary = "Saved FlowState Restoration Points:\n" + "\n".join([
                                    f"• {w['name']} ({w['apps_count']} apps, {w['tabs_count']} tabs, created {w['created_str']})"
                                    for w in workspaces
                                ])
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="Saved Workspaces", output=summary, percent=100)
                                self.speak(f"You have {len(workspaces)} saved workspaces: {', '.join(names[:3])}, sir.")
                            else:
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="No Workspaces", output="No saved FlowState restoration points found.", percent=100)
                                self.speak("You don't have any saved workspace restoration points yet, sir.")

                    except Exception as exc:
                        self.ui.write_log(f"ERR: FlowState failed: {exc}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="FlowState Error", output=str(exc), percent=0)
                        self.speak(f"FlowState encountered an error: {exc}")

                threading.Thread(target=_run_flowstate, daemon=True).start()
                return

            if intent_res.intent == "omni_planner":
                plan_goal = str(intent_res.parameters.get("goal") or text)
                self.speak(intent_res.voice_ack or "Executing multi-step system plan...")

                def _run_omni_planner():
                    try:
                        from core.omni_planner import get_omni_planner
                        planner = get_omni_planner()
                        steps = planner.decompose_goal(plan_goal)
                        step_descs = [f"{s.subsystem.capitalize()}: {s.description}" for s in steps]

                        if hasattr(self.ui, "begin_task_workspace"):
                            self.ui.begin_task_workspace(
                                f"OmniPlanner: {plan_goal[:35]}",
                                step_descs,
                                source=source or "local"
                            )

                        report = planner.execute_plan(plan_goal, steps=steps)

                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(
                                status=f"Completed {report.successful_steps}/{report.total_steps} Steps",
                                output=report.executive_briefing,
                                percent=100
                            )

                        self.speak(report.executive_briefing)

                    except Exception as exc:
                        self.ui.write_log(f"ERR: OmniPlanner failed: {exc}")
                        self.speak(f"OmniPlanner encountered an issue: {exc}")

                threading.Thread(target=_run_omni_planner, daemon=True, name="omni-planner").start()
                return

            if intent_res.intent == "reverse_engineer":
                target = str(intent_res.parameters.get("target") or text)
                action = str(intent_res.action or intent_res.parameters.get("action") or "analyze")
                feature = str(intent_res.parameters.get("feature") or "")
                dest = str(intent_res.parameters.get("destination") or "")
                self.speak(intent_res.voice_ack or "Initiating reverse engineering...")
                if hasattr(self.ui, "begin_task_workspace"):
                    self.ui.begin_task_workspace(
                        f"Reverse Engineering: {target[:30]}",
                        ["Connecting to target", "Inspecting DOM / Binary layout", "Extracting API surface & schemas", "Synthesizing output"],
                        source=source or "local"
                    )

                def _run_re():
                    try:
                        from actions.reverse_engineer import reverse_engineer
                        res = reverse_engineer(
                            {"target": target, "action": action, "feature": feature, "destination": dest},
                            player=self.ui,
                            speak=self.speak
                        )
                        self.ui.write_log(res)
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Complete", output=res[:300], percent=100)
                    except Exception as exc:
                        self.ui.write_log(f"ERR: Reverse engineering failed: {exc}")
                        self.speak(f"Reverse engineering encountered an error: {exc}")

                threading.Thread(target=_run_re, daemon=True, name="reverse-engineer-worker").start()
                return

            if intent_res.intent == "generate_image":
                img_prompt = str(intent_res.parameters.get("prompt") or text)
                img_style = str(intent_res.parameters.get("style") or "photorealistic")
                self.speak(intent_res.voice_ack or "Generating your image now, sir...")
                if hasattr(self.ui, "begin_task_workspace"):
                    self.ui.begin_task_workspace(
                        f"Image Synthesis: {img_prompt[:25]}",
                        ["Refining neural diffusion prompt", "Synthesizing high-res image", "Saving to Desktop", "Rendering HUD preview"],
                        source=source or "local"
                    )

                def _run_img():
                    try:
                        from actions.image_generator import generate_image
                        res = generate_image(
                            {"prompt": img_prompt, "style": img_style},
                            player=self.ui,
                            speak=self.speak
                        )
                        self.ui.write_log(res)
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Render Complete", output="Saved to Desktop/Nexus_Images", percent=100)
                    except Exception as exc:
                        self.ui.write_log(f"ERR: Image generation failed: {exc}")
                        self.speak(f"Image generation encountered an error: {exc}")

                threading.Thread(target=_run_img, daemon=True, name="image-gen-worker").start()
                return

            if intent_res.intent == "study_guard":
                sg_action = str(intent_res.action or "start").lower()
                sg_duration = int(intent_res.parameters.get("duration", 25))
                sg_subject = str(intent_res.parameters.get("subject", "Focus Sprint"))
                sg_lofi = bool(intent_res.parameters.get("lofi", False))
                sg_timer_only = bool(intent_res.parameters.get("timer_only", False))

                if sg_action not in ("start", "begin", "launch"):
                    self.speak(intent_res.voice_ack or "Processing StudyGuard...")

                def _run_study_guard():
                    try:
                        from core.study_guard import get_study_guard_manager
                        manager = get_study_guard_manager()

                        if sg_action in ("start", "begin", "launch"):
                            def _hud_update(status_text: str, pct: int):
                                try:
                                    if hasattr(self.ui, "update_task_workspace"):
                                        self.ui.update_task_workspace(status=status_text, percent=pct)
                                except Exception:
                                    pass

                            res = manager.start_session(
                                duration_minutes=sg_duration,
                                subject=sg_subject,
                                play_lofi=sg_lofi,
                                timer_only=sg_timer_only,
                                speak_cb=self.speak,
                                hud_update_cb=_hud_update
                            )
                            if res.get("success"):
                                mode_lbl = "Pomodoro Focus Timer" if sg_timer_only else "MediaPipe Face Sentinel"
                                if hasattr(self.ui, "begin_task_workspace"):
                                    self.ui.begin_task_workspace(
                                        f"StudyGuard: {sg_subject} ({sg_duration}m)",
                                        [
                                            f"Mode: {mode_lbl}",
                                            "Track Eye Aspect Ratio & posture" if not sg_timer_only else "Pomodoro countdown active",
                                            "Monitor distractions & flow state" if not sg_timer_only else "Silent focus interval",
                                            "Log sprint analytics to Circuit HUD"
                                        ],
                                        source=source or "local"
                                    )
                                self.speak(res.get("message", f"Study session started for {sg_duration} minutes."))
                            else:
                                err_msg = res.get("message", "Study session could not start.")
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="Startup Blocked", output=err_msg, percent=0)
                                self.speak(err_msg)

                        elif sg_action in ("stop", "end", "finish"):
                            res = manager.stop_session()
                            if res.get("success"):
                                stats = res.get("stats", {})
                                card_path = res.get("card_path")
                                summary = res.get("summary", "")
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="Session Finished", output=summary, percent=100)
                                if hasattr(self.ui, "show_hud_deliverable"):
                                    self.ui.show_hud_deliverable(
                                        title=f"Study: {stats.get('subject', 'Sprint')}",
                                        summary=f"Focus Efficiency: {stats.get('focus_score')}%\nTotal Time: {int(stats.get('total_seconds', 0) // 60)}m",
                                        bullets=[
                                            f"Focus Score: {stats.get('focus_score')}%",
                                            f"Focus Time: {int(stats.get('active_focus_seconds', 0) // 60)} minutes",
                                            f"Sleep Alerts: {stats.get('sleep_alerts', 0)}",
                                            f"Phone Distractions: {stats.get('phone_alerts', 0)}",
                                        ],
                                        file_path=card_path,
                                        kind="study_guard"
                                    )
                                self.speak(f"Study session finished, sir! Your focus score was {stats.get('focus_score')} percent.")
                            else:
                                self.speak(res.get("message", "No active study session to stop."))

                        elif sg_action in ("pause", "hold"):
                            manager.pause_session()

                        elif sg_action in ("resume", "continue"):
                            manager.resume_session()

                        elif sg_action in ("status", "stats"):
                            st = manager.get_status()
                            if st.get("is_active"):
                                stats = st.get("stats", {})
                                self.speak(f"Session '{stats.get('subject')}' is active with a focus score of {stats.get('focus_score')} percent, sir.")
                            else:
                                self.speak("No study session is currently running, sir.")

                    except Exception as exc:
                        self.ui.write_log(f"ERR: StudyGuard failed: {exc}")
                        self.speak(f"StudyGuard encountered an issue: {exc}")

                threading.Thread(target=_run_study_guard, daemon=True, name="study-guard").start()
                return

            if intent_res.intent == "game_sentinel":
                gs_action = str(intent_res.action or "clean_ram").lower()
                gs_game = str(intent_res.parameters.get("game_name") or "Gaming Session")

                def _run_game_sentinel():
                    try:
                        from core.game_sentinel import get_game_sentinel_manager
                        manager = get_game_sentinel_manager()

                        if gs_action in ("start", "enable", "on", "activate", "boost"):
                            if hasattr(self.ui, "begin_task_workspace"):
                                self.ui.begin_task_workspace(
                                    f"Game Sentinel: {gs_game}",
                                    [
                                        "Engage Ultimate Performance Power Plan",
                                        "Elevate game process thread priority to High",
                                        "Execute Mem Reduct deep memory & standby purge",
                                        "Silence non-critical desktop notifications"
                                    ],
                                    source=source or "local"
                                )
                            res = manager.activate_game_mode(game_name=gs_game, manual=True, speak=False)
                            ram_freed = res.get("ram_cleaned", {}).get("freed_mb", 0)
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(
                                    status="Turbo Boost Engaged",
                                    output=f"RAM Purged: {ram_freed} MB | Power: {res.get('power_plan')} | Priority: HIGH",
                                    percent=100
                                )
                            self.speak(res.get("message"))

                        elif gs_action in ("stop", "disable", "off", "deactivate", "exit"):
                            res = manager.deactivate_game_mode(manual=True, speak=False)
                            if res.get("success"):
                                if hasattr(self.ui, "update_task_workspace"):
                                    self.ui.update_task_workspace(status="Game Mode Disengaged", percent=100)
                                self.speak(res.get("message"))
                            else:
                                self.speak("Game mode is not currently active, sir.")

                        elif gs_action in ("clean_ram", "purge_ram", "mem_reduct", "free_ram", "clear_ram"):
                            if hasattr(self.ui, "begin_task_workspace"):
                                self.ui.begin_task_workspace(
                                    "Mem Reduct RAM Cleaner",
                                    [
                                        "Query system working sets & processes",
                                        "Empty process working sets via K32EmptyWorkingSet",
                                        "Purge Windows Standby List & Modified Page List",
                                        "Calculate freed physical memory"
                                    ],
                                    source=source or "local"
                                )
                            res = manager.clean_ram_now(speak=False)
                            stats = res.get("stats", {})
                            if hasattr(self.ui, "finish_task_workspace"):
                                self.ui.finish_task_workspace(
                                    result=res.get("message"),
                                    status=f"Freed {stats.get('freed_mb', 0)} MB ({stats.get('before_percent')}% -> {stats.get('after_percent')}%)",
                                    percent=100
                                )
                            self.speak(res.get("message"))

                        elif gs_action in ("status", "telemetry"):
                            st = manager.get_status()
                            act = "Active" if st.get("is_game_mode_active") else "Idle"
                            gname = f" for '{st.get('active_game_name')}'" if st.get("active_game_name") else ""
                            self.speak(f"Game Sentinel is {act}{gname}. RAM usage is at {st.get('ram_percent')} percent.")

                    except Exception as exc:
                        self.ui.write_log(f"ERR: Game Sentinel failed: {exc}")
                        self.speak(f"Game Sentinel encountered an issue: {exc}")

                threading.Thread(target=_run_game_sentinel, daemon=True, name="game-sentinel").start()
                return

            if intent_res.intent == "net_sentinel":
                ns_action = str(intent_res.action or "scan_network").lower()
                ns_target = str(intent_res.parameters.get("target") or "")
                self.speak(intent_res.voice_ack or "Executing NetSentinel...")

                def _run_net_sentinel():
                    try:
                        from core.net_sentinel import get_net_sentinel
                        sentinel = get_net_sentinel()

                        if ns_action in ("scan_network", "scan_wifi", "scan_lan", "devices", "radar"):
                            # Immediately pop up the tactical Net-Radar in active sweep mode
                            if hasattr(self.ui, "show_radar_hud"):
                                self.ui.show_radar_hud(sentinel.last_scan_result or {})

                            if hasattr(self.ui, "begin_task_workspace"):
                                self.ui.begin_task_workspace(
                                    "NetSentinel: Subnet Topology Audit",
                                    [
                                        "Activate Ultron Net-Radar Scope",
                                        "Sweep /24 subnet addresses via SendARP",
                                        "Resolve OUI hardware vendors & open service ports",
                                        "Render interactive Cyberpunk Network Map"
                                    ],
                                    source=source or "local"
                                )
                            res = sentinel.scan_local_network(deep=False)
                            card_path = res.get("card_path")
                            num_devs = res.get("total_devices_found", 0)
                            gw_ip = res.get("gateway_ip", "192.168.0.1")
                            router_vendor = res.get("router", {}).get("vendor", "Router")

                            # Push live discovered devices to the Radar HUD
                            if hasattr(self.ui, "show_radar_hud"):
                                self.ui.show_radar_hud(res)

                            summary_msg = f"Network scan complete: Discovered {num_devs} active devices on your LAN through gateway {gw_ip} ({router_vendor})."
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(
                                    status=f"{num_devs} Devices Online",
                                    output=summary_msg,
                                    percent=100
                                )
                            if card_path and hasattr(self.ui, "show_hud_deliverable"):
                                self.ui.show_hud_deliverable(
                                    title=f"Network Topology: {gw_ip}",
                                    summary=f"Discovered {num_devs} connected devices on {res.get('subnet')}",
                                    bullets=[
                                        f"Gateway: {gw_ip} ({router_vendor})",
                                        f"Public IP: {res.get('internet', {}).get('public_ip')}",
                                        f"ISP: {res.get('internet', {}).get('isp')}",
                                        f"Active LAN Nodes: {num_devs}",
                                    ],
                                    file_path=str(card_path),
                                    kind="net_sentinel"
                                )
                            self.speak(f"Scan complete, sir. Discovered {num_devs} devices connected to your {router_vendor} router. Radar scope is active.")

                        elif ns_action in ("connect_all_devices", "connect_all", "link_devices", "mesh_connect", "broadcast_online"):
                            # Immediately display the tactical Radar HUD
                            if hasattr(self.ui, "show_radar_hud"):
                                self.ui.show_radar_hud(sentinel.last_scan_result or {})

                            if hasattr(self.ui, "begin_task_workspace"):
                                self.ui.begin_task_workspace(
                                    "NetSentinel: Zero-Touch Mesh Sync",
                                    [
                                        "Broadcast Nexus Core Online beacon across subnet",
                                        "Probe SSDP, Cast & UPnP services on LAN endpoints",
                                        "Establish zero-install device telemetry mesh",
                                        "Synchronize Radar HUD device status"
                                    ],
                                    source=source or "local"
                                )

                            c_res = sentinel.connect_all_devices("Nexus AI Online // Node Linked")
                            linked_devs = c_res.get("total_devices_linked", 0)

                            # Push updated linked devices to Radar HUD
                            if hasattr(self.ui, "show_radar_hud"):
                                self.ui.show_radar_hud(sentinel.last_scan_result or {})

                            msg = f"Network mesh online: Connected {linked_devs} devices. Broadcast notification transmitted across LAN."
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(
                                    status=f"{linked_devs} Devices Linked",
                                    output=msg,
                                    percent=100
                                )
                            self.speak(f"Network mesh synchronized, sir. Linked with {linked_devs} devices across your network. Online notification broadcasted.")

                        elif ns_action in ("inspect_router", "router"):
                            res = sentinel.inspect_router()
                            open_p = res.get("open_ports", [])
                            r_msg = (
                                f"Router at {res.get('gateway_ip')} is a {res.get('vendor')} gateway. "
                                f"Open ports: {open_p}. Web administration console is active."
                            )
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(status=f"Router: {res.get('vendor')}", output=r_msg, percent=100)
                            self.speak(r_msg)

                        elif ns_action in ("internet_status", "internet", "public_ip"):
                            tele = sentinel.get_internet_telemetry()
                            stat = "Online" if tele.get("connected") else "Offline"
                            i_msg = (
                                f"Internet uplink is {stat}, sir. Public IP is {tele.get('public_ip')} "
                                f"via {tele.get('isp')} in {tele.get('city')}, with {tele.get('ping_latency_ms')} milliseconds latency."
                            )
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(status=f"Internet: {stat}", output=i_msg, percent=100)
                            self.speak(i_msg)

                        elif ns_action in ("wake_device", "wake_on_lan"):
                            if not ns_target:
                                self.speak("Please specify the target MAC address to wake, sir.")
                                return
                            w_res = sentinel.wake_on_lan(ns_target)
                            self.speak(w_res.get("message", "Wake-on-LAN packet transmitted."))

                        elif ns_action == "ping":
                            p_res = sentinel.ping_target(ns_target or "1.1.1.1")
                            p_msg = f"Host {p_res.get('target')} is {p_res.get('status')} with average latency of {p_res.get('avg_latency_ms')} milliseconds."
                            self.speak(p_msg)

                    except Exception as exc:
                        self.ui.write_log(f"ERR: NetSentinel failed: {exc}")
                        self.speak(f"NetSentinel encountered an issue: {exc}")

                threading.Thread(target=_run_net_sentinel, daemon=True, name="net-sentinel").start()
                return

            if intent_res.intent == "space_cleaner":
                sc_action = str(intent_res.action or "open_sentinel").lower()
                self.speak(intent_res.voice_ack or "Initializing Nexus Storage Sentinel...")

                def _run_space_cleaner():
                    try:
                        from core.space_cleaner import get_space_cleaner
                        cleaner = get_space_cleaner()

                        # Pop up Storage Sentinel HUD overlay or standalone window
                        if hasattr(self.ui, "show_space_cleaner_hud"):
                            self.ui.show_space_cleaner_hud()
                        else:
                            from core.space_cleaner_hud import show_space_cleaner_hud
                            show_space_cleaner_hud()

                        if hasattr(self.ui, "begin_task_workspace"):
                            self.ui.begin_task_workspace(
                                "Storage Sentinel: Interactive Disk Audit",
                                [
                                    "Project Radial Sunburst Storage Topography",
                                    "Audit System Temp, Browser Shader Caches & Crash Logs",
                                    "Calculate Safe Reclaimable Clusters",
                                    "Safely Purge Volatile Bloat"
                                ],
                                source=source or "local"
                            )

                        telemetry = cleaner.get_disk_telemetry()
                        drives = telemetry.get("drives", [])
                        primary_drive = drives[0] if drives else {}
                        free_gb = primary_drive.get("free_gb", 0)
                        total_gb = primary_drive.get("total_gb", 0)
                        pct_used = primary_drive.get("percent_used", 0)

                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(
                                status=f"{free_gb} GB Free / {total_gb} GB Total",
                                output=f"Storage Sentinel active. Primary disk has {free_gb} GB free ({100 - pct_used:.1f}% available). Interactive Sunburst scope ready.",
                                percent=100
                            )
                    except Exception as exc:
                        self.ui.write_log(f"ERR: Storage Sentinel failed: {exc}")
                        self.speak(f"Storage Sentinel encountered an issue: {exc}")

                threading.Thread(target=_run_space_cleaner, daemon=True, name="space-cleaner").start()
                return

            if intent_res.intent == "presentation":
                presentation_topic = str(intent_res.parameters.get("topic") or text)
                self.speak(intent_res.voice_ack or "Designing your presentation slides...")
                if hasattr(self.ui, "begin_task_workspace"):
                    self.ui.begin_task_workspace(
                        text,
                        ["Researching topic", "Outlining slides", "Applying typography & theme", "Generating PowerPoint deck"],
                        source=source or "local"
                    )
                def _run_presentation():
                    try:
                        from actions.office_generator import generate_presentation_from_prompt
                        res = generate_presentation_from_prompt(presentation_topic, player=self.ui, speak=self.speak)
                        self.ui.write_log(f"[NexusOffice] {res}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Presentation Completed", output=res, percent=100)
                        self.speak("Your presentation has been created and saved to Desktop, sir.")
                    except Exception as exc:
                        self.ui.write_log(f"ERR: Presentation generation failed: {exc}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Generation Failed", output=str(exc), percent=0)
                        self.speak("There was an issue creating the presentation, sir. Please check the logs.")
                threading.Thread(target=_run_presentation, daemon=True).start()
                return

            if intent_res.intent == "spreadsheet":
                sheet_topic = str(intent_res.parameters.get("topic") or text)
                self.speak(intent_res.voice_ack or "Building your spreadsheet workbook...")
                if hasattr(self.ui, "begin_task_workspace"):
                    self.ui.begin_task_workspace(
                        text,
                        ["Analyzing data structure", "Defining headers & formulas", "Formatting workbook", "Saving Excel spreadsheet"],
                        source=source or "local"
                    )
                def _run_spreadsheet():
                    try:
                        from actions.office_generator import generate_spreadsheet_from_prompt
                        res = generate_spreadsheet_from_prompt(sheet_topic, player=self.ui, speak=self.speak)
                        self.ui.write_log(f"[NexusOffice] {res}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Spreadsheet Completed", output=res, percent=100)
                        self.speak("Your spreadsheet workbook has been created and saved to Desktop, sir.")
                    except Exception as exc:
                        self.ui.write_log(f"ERR: Spreadsheet generation failed: {exc}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Generation Failed", output=str(exc), percent=0)
                        self.speak("There was an issue creating the spreadsheet, sir. Please check the logs.")
                threading.Thread(target=_run_spreadsheet, daemon=True).start()
                return

            if intent_res.intent == "developer_agent":
                developer_settings = self.ui._load_app_settings() if hasattr(self.ui, "_load_app_settings") else {}
                developer_workspace = str(developer_settings.get("developer_mode_workspace", "")).strip()
                if not developer_workspace:
                    developer_workspace = str(Path.home() / "Desktop" / "NexusProjects")
                    Path(developer_workspace).mkdir(parents=True, exist_ok=True)

                self.speak(intent_res.voice_ack or "Working on your project with Nexus Dev...")
                if hasattr(self.ui, "begin_task_workspace"):
                    self.ui.begin_task_workspace(text, ["Analyzing specifications", "Scaffolding files", "Writing code", "Verifying build"], source=source or "local")

                def _run_brahma_dev():
                    try:
                        import webbrowser
                        from actions.nexus_dev_agent import run_dev_agent
                        res = run_dev_agent({
                            "description": text,
                            "workspace_path": developer_workspace
                        }, speak=self.speak)
                        self.ui.write_log(f"[NexusDev] {res[:400]}")
                        if "encountered an error during inference" in res or "LLM error:" in res:
                            if hasattr(self.ui, "update_task_workspace"):
                                self.ui.update_task_workspace(status="Build Error", output=res, percent=0)
                            self.speak("There was an error building the project, sir. Please check the logs.")
                            return
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Project Completed", output=res, percent=100)
                        folder_display = developer_workspace
                        try:
                            folder_display = Path(developer_workspace).name or developer_workspace
                        except Exception:
                            pass
                        self.speak(f"Your project has been completed and saved to {folder_display}, sir.")
                        try:
                            idx_path = Path(developer_workspace) / "index.html"
                            if idx_path.exists():
                                webbrowser.open(str(idx_path.resolve()))
                        except Exception:
                            pass
                    except Exception as exc:
                        self.ui.write_log(f"ERR: Nexus Dev failed: {exc}")
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Build Failed", output=str(exc), percent=0)
                        self.speak("There was an issue building the project, sir. Please check the logs.")
                threading.Thread(target=_run_brahma_dev, daemon=True).start()
                return

        except Exception as _dispatcher_exc:
            print(f"[Dispatcher] Warning: Intent dispatcher error, falling back to legacy rules: {_dispatcher_exc}")

        # Check for dynamic/evolved skill execution (e.g. specialized installed skills)
        try:
            from core.dynamic_registry import DynamicToolRegistry
            matched = DynamicToolRegistry.find_matching_skill(text)
            if matched:
                skill_name, skill_args = matched
                self.speak(f"Running {skill_name.replace('_', ' ')}.")
                def _run_dynamic_feature():
                    try:
                        res = DynamicToolRegistry.execute_sync(skill_name, skill_args or {})
                        out_text = ""
                        if isinstance(res, dict):
                            out_text = str(res.get("summary") or res.get("output") or res.get("text") or res).strip()
                        else:
                            out_text = str(res).strip()
                        self.ui.write_log(f"Nexus Core [{skill_name}]:\n{out_text}")
                        if hasattr(self.ui, "finish_task_workspace"):
                            self.ui.finish_task_workspace(out_text, f"{skill_name} completed.", 100)
                        if hasattr(self.ui, "show_hud_deliverable"):
                            self.ui.show_hud_deliverable(
                                title=f"{skill_name.upper()} DELIVERABLE",
                                summary=out_text,
                                kind=skill_name
                            )
                        # Speak first line as voice response
                        first_line = out_text.strip().splitlines()[0] if out_text.strip() else "Task completed."
                        if len(first_line) > 120:
                            first_line = first_line[:115] + "..."
                        self.speak(first_line)
                    except Exception as err:
                        self.ui.write_log(f"ERR: {skill_name} failed: {err}")
                        self.speak(f"Error running {skill_name}: {err}")
                threading.Thread(target=_run_dynamic_feature, daemon=True, name=f"skill-{skill_name}").start()
                return
        except Exception as e_dyn:
            print(f"[Registry] Match error: {e_dyn}")

        # Nexus Connect Mobile Routing (fallback intercept)
        if source != "instagram" and self._handle_nexus_connect_command(text, source=source or "local"):
            return

        developer_settings = self.ui._load_app_settings() if hasattr(self.ui, "_load_app_settings") else {}
        developer_workspace = str(developer_settings.get("developer_mode_workspace", "")).strip()
        if not developer_workspace:
            developer_workspace = str(Path.home() / "Desktop" / "NexusProjects")
            Path(developer_workspace).mkdir(parents=True, exist_ok=True)

        presentation_request = _looks_like_presentation_request(text)
        spreadsheet_request = _looks_like_spreadsheet_request(text)

        if presentation_request:
            self.speak("Designing your presentation slides...")
            if hasattr(self.ui, "begin_task_workspace"):
                self.ui.begin_task_workspace(
                    text,
                    ["Researching topic", "Outlining slides", "Applying typography & theme", "Generating PowerPoint deck"],
                    source=source or "local"
                )

            def _run_presentation():
                try:
                    from actions.office_generator import generate_presentation_from_prompt
                    res = generate_presentation_from_prompt(text, player=self.ui, speak=self.speak)
                    self.ui.write_log(f"[NexusOffice] {res}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Presentation Completed", output=res, percent=100)
                    self.speak("Your presentation has been created and saved to Desktop, sir.")
                except Exception as exc:
                    self.ui.write_log(f"ERR: Presentation generation failed: {exc}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Generation Failed", output=str(exc), percent=0)
                    self.speak("There was an issue creating the presentation, sir. Please check the logs.")

            threading.Thread(target=_run_presentation, daemon=True).start()
            return

        if spreadsheet_request:
            self.speak("Building your spreadsheet workbook...")
            if hasattr(self.ui, "begin_task_workspace"):
                self.ui.begin_task_workspace(
                    text,
                    ["Analyzing data structure", "Defining headers & formulas", "Formatting workbook", "Saving Excel spreadsheet"],
                    source=source or "local"
                )

            def _run_spreadsheet():
                try:
                    from actions.office_generator import generate_spreadsheet_from_prompt
                    res = generate_spreadsheet_from_prompt(text, player=self.ui, speak=self.speak)
                    self.ui.write_log(f"[NexusOffice] {res}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Spreadsheet Completed", output=res, percent=100)
                    self.speak("Your spreadsheet workbook has been created and saved to Desktop, sir.")
                except Exception as exc:
                    self.ui.write_log(f"ERR: Spreadsheet generation failed: {exc}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Generation Failed", output=str(exc), percent=0)
                    self.speak("There was an issue creating the spreadsheet, sir. Please check the logs.")

            threading.Thread(target=_run_spreadsheet, daemon=True).start()
            return

        website_request = _looks_like_website_request(text)
        code_request = (not presentation_request and not spreadsheet_request) and _looks_like_code_request(text) and any(re.search(rf"\b{re.escape(w)}\b", text.lower()) for w in ("app", "website", "web", "program", "script", "project", "game", "calc", "html", "react"))

        if website_request or code_request:
            self.speak("Working on your project with Nexus Dev...")
            if hasattr(self.ui, "begin_task_workspace"):
                self.ui.begin_task_workspace(text, ["Analyzing specifications", "Scaffolding files", "Writing code", "Verifying build"], source=source or "local")

            def _run_brahma_dev():
                try:
                    import webbrowser
                    from actions.nexus_dev_agent import run_dev_agent
                    res = run_dev_agent({
                        "description": text,
                        "workspace_path": developer_workspace
                    }, speak=self.speak)
                    self.ui.write_log(f"[BrahmaDev] {res[:400]}")

                    if "encountered an error during inference" in res or "LLM error:" in res:
                        if hasattr(self.ui, "update_task_workspace"):
                            self.ui.update_task_workspace(status="Build Error", output=res, percent=0)
                        self.speak("There was an error building the project, sir. Please check the logs.")
                        return

                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Project Completed", output=res, percent=100)

                    folder_display = developer_workspace
                    try:
                        folder_display = Path(developer_workspace).name or developer_workspace
                    except Exception:
                        pass

                    self.speak(f"Your project has been completed and saved to {folder_display}, sir.")

                    # Auto-open index.html in browser if created
                    try:
                        idx_path = Path(developer_workspace) / "index.html"
                        if idx_path.exists():
                            webbrowser.open(str(idx_path.resolve()))
                    except Exception:
                        pass
                except Exception as exc:
                    self.ui.write_log(f"ERR: Nexus Dev failed: {exc}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Build Failed", output=str(exc), percent=0)
                    self.speak("There was an issue building the project, sir. Please check the logs.")

            threading.Thread(target=_run_brahma_dev, daemon=True).start()
            return

        # Google Workspace Direct Command Handling (Gmail & Calendar checks)
        lower_cmd = text.lower().strip()
        is_email_check = any(phrase in lower_cmd for phrase in ("check email", "check my email", "unread email", "read email", "my inbox", "check inbox", "show emails"))
        is_calendar_check = any(phrase in lower_cmd for phrase in ("my schedule", "what's on my calendar", "check calendar", "my meetings", "schedule today", "events today"))

        if is_email_check:
            self.speak("Checking your Gmail inbox, sir...")
            if hasattr(self.ui, "begin_task_workspace"):
                self.ui.begin_task_workspace(
                    text,
                    ["Connecting to Gmail", "Fetching unread messages", "Parsing headers & body", "Summarizing inbox"],
                    source=source or "local"
                )
            def _run_gw_email():
                try:
                    from actions.google_workspace_mcp import google_workspace
                    res = google_workspace({"service": "gmail", "action": "unread"}, player=self.ui, speak=self.speak)
                    self.ui.write_log(f"[GoogleWorkspace] {res}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Email Check Completed", output=res, percent=100)
                    self.speak("Here are your latest emails, sir.")
                except Exception as exc:
                    self.ui.write_log(f"ERR: Gmail check failed: {exc}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Email Check Failed", output=str(exc), percent=0)
                    self.speak("Unable to check emails. Please ensure your credentials are set up in Settings.")
            threading.Thread(target=_run_gw_email, daemon=True).start()
            return

        if is_calendar_check:
            self.speak("Checking your calendar schedule...")
            if hasattr(self.ui, "begin_task_workspace"):
                self.ui.begin_task_workspace(
                    text,
                    ["Connecting to Calendar", "Retrieving scheduled events", "Formatting timeline"],
                    source=source or "local"
                )
            def _run_gw_calendar():
                try:
                    from actions.google_workspace_mcp import google_workspace
                    res = google_workspace({"service": "calendar", "action": "list"}, player=self.ui, speak=self.speak)
                    self.ui.write_log(f"[GoogleWorkspace] {res}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Schedule Retrieved", output=res, percent=100)
                    self.speak("Here is your schedule, sir.")
                except Exception as exc:
                    self.ui.write_log(f"ERR: Calendar check failed: {exc}")
                    if hasattr(self.ui, "update_task_workspace"):
                        self.ui.update_task_workspace(status="Schedule Check Failed", output=str(exc), percent=0)
                    self.speak("There was an issue checking your schedule, sir.")
            threading.Thread(target=_run_gw_calendar, daemon=True).start()
            return

        # OS Hardware & Diagnostics Direct Command Handling (0 background API credits)
        is_ram_check = any(p in lower_cmd for p in ("eating my ram", "ram hogs", "memory hogs", "check ram", "ram usage", "memory usage", "who is using ram"))
        is_battery_check = any(p in lower_cmd for p in ("battery health", "check battery", "battery status", "battery percentage", "is laptop charging", "how much battery"))
        is_brightness_req = any(p in lower_cmd for p in ("dim screen", "dim monitor", "increase brightness", "lower brightness", "set brightness", "screen brightness"))
        is_kill_req = (lower_cmd.startswith("kill ") or lower_cmd.startswith("terminate ") or lower_cmd.startswith("force kill ")) and len(lower_cmd.split()) <= 4
        is_diag_req = any(p in lower_cmd for p in ("system status", "system diagnostics", "hardware status", "computer vitals", "pc diagnostics"))

        if is_ram_check:
            self.speak("Scanning memory consumers...")
            def _run_ram():
                from actions.system_diagnostics_mcp import system_diagnostics
                res = system_diagnostics({"action": "ram_hogs"}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[Diagnostics] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Memory analysis complete.", 100)
            threading.Thread(target=_run_ram, daemon=True).start()
            return

        if is_battery_check:
            def _run_battery():
                from actions.system_diagnostics_mcp import system_diagnostics
                res = system_diagnostics({"action": "battery"}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[Diagnostics] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Battery check complete.", 100)
            threading.Thread(target=_run_battery, daemon=True).start()
            return

        if is_brightness_req:
            import re
            m = re.search(r"(\d+)", lower_cmd)
            lvl = int(m.group(1)) if m else None
            rel = "dim" in lower_cmd or "lower" in lower_cmd or "increase" in lower_cmd or "boost" in lower_cmd
            if rel and lvl is None:
                lvl = -20 if ("dim" in lower_cmd or "lower" in lower_cmd) else 20
            def _run_brightness():
                from actions.system_diagnostics_mcp import system_diagnostics
                p = {"action": "brightness"}
                if lvl is not None:
                    p["level"] = lvl
                    p["relative"] = rel
                res = system_diagnostics(p, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[Diagnostics] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Brightness adjusted.", 100)
            threading.Thread(target=_run_brightness, daemon=True).start()
            return

        if is_kill_req:
            target_app = lower_cmd.split(None, 1)[1].strip()
            def _run_kill():
                from actions.system_diagnostics_mcp import system_diagnostics
                res = system_diagnostics({"action": "kill", "target": target_app, "force": "force" in lower_cmd}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[Diagnostics] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Process management complete.", 100)
            threading.Thread(target=_run_kill, daemon=True).start()
            return

        if is_diag_req:
            self.speak("Retrieving system diagnostics report...")
            def _run_diag():
                from actions.system_diagnostics_mcp import system_diagnostics
                res = system_diagnostics({"action": "status"}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[Diagnostics] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "System report ready.", 100)
            threading.Thread(target=_run_diag, daemon=True).start()
            return

        # Autonomous Self-Healing & Continuous Learning Fast-Path
        is_trigger_bug = any(p in lower_cmd for p in ("trigger test bug", "simulate bug", "test bug", "create bug", "simulate error", "trigger error", "break test"))
        is_heal_cmd = any(p in lower_cmd for p in ("fix that bug", "fix the bug", "heal yourself", "auto heal", "patch yourself", "fix error", "fix this error"))
        is_rollback_cmd = any(p in lower_cmd for p in ("undo last patch", "rollback patch", "revert patch", "undo patch"))
        is_patch_history = any(p in lower_cmd for p in ("patch history", "patch log", "show patches", "auto heal status"))
        is_learn_rule = (
            lower_cmd.startswith("remember to ") or 
            lower_cmd.startswith("remember that ") or 
            (lower_cmd.startswith("always ") and len(lower_cmd.split()) > 2 and not lower_cmd.startswith("always open")) or
            (lower_cmd.startswith("never ") and len(lower_cmd.split()) > 2) or
            "new rule:" in lower_cmd
        )

        if is_trigger_bug:
            def _run_test_bug():
                try:
                    from actions.test_action import test_action
                    res = test_action({}, player=self.ui, speak=self.speak)
                    self.ui.write_log(f"[TestAction] {res}")
                    self.speak(f"Test action executed with no errors: {res}. The code is currently healthy.")
                except Exception as exc:
                    import traceback
                    from actions.auto_heal_engine import AutoHealEngine
                    tb_str = traceback.format_exc()
                    AutoHealEngine.record_last_error(tb_str)
                    # Ultron Autonomous Self-Repair: Immediately heals without asking for permission!
                    AutoHealEngine.heal_traceback(
                        tb_str,
                        player=self.ui,
                        speak=self.speak,
                        module_name="test_action"
                    )
            threading.Thread(target=_run_test_bug, daemon=True).start()
            return

        if is_heal_cmd:
            def _run_heal():
                from actions.auto_heal_engine import auto_heal
                res = auto_heal({"action": "heal"}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[AutoHeal] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Self-patching complete.", 100)
            threading.Thread(target=_run_heal, daemon=True).start()
            return

        if is_rollback_cmd:
            def _run_rollback():
                from actions.auto_heal_engine import auto_heal
                res = auto_heal({"action": "rollback"}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[AutoHeal] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Rollback complete.", 100)
            threading.Thread(target=_run_rollback, daemon=True).start()
            return

        if is_patch_history:
            def _run_history():
                from actions.auto_heal_engine import auto_heal
                action_type = "status" if "status" in lower_cmd else "history"
                res = auto_heal({"action": action_type}, player=self.ui, speak=self.speak)
                self.ui.write_log(f"[AutoHeal] {res}")
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(res, "Auto-heal report ready.", 100)
            threading.Thread(target=_run_history, daemon=True).start()
            return

        # Continuous Self-Improvement: Conversational Correction Learner
        from core.learned_rules import LearnedRulesEngine
        detected_rule = LearnedRulesEngine.detect_and_learn_conversational_rule(text)
        if detected_rule or is_learn_rule:
            rule_text = (detected_rule.get("rule") if detected_rule else None) or lower_cmd.replace("remember that ", "").replace("remember to ", "").replace("new rule: ", "").strip()
            def _run_learn():
                res = LearnedRulesEngine.add_rule(rule_text, origin="conversational_dialogue")
                msg = res.get("message", f"Understood. I have adapted my behavioral directive: {rule_text}")
                self.speak(f"Understood, sir. I have adapted my behavioral directive: {rule_text}")
                self.ui.write_log(f"🧠 [Continuous Learning] Rule recorded: {rule_text}")
                if hasattr(self.ui, "show_hud_deliverable"):
                    self.ui.show_hud_deliverable(
                        title="Behavioral Directive Learned",
                        summary=rule_text,
                        bullets=[f"Rule: {rule_text}", "Origin: Continuous Dialogue", "Status: Active in LLM context"],
                        kind="rule"
                    )
                if hasattr(self.ui, "finish_task_workspace"):
                    self.ui.finish_task_workspace(msg, "Rule learned.", 100)
            threading.Thread(target=_run_learn, daemon=True).start()
            return

        # Local PC Volume Control (Speakers)
        is_volume_cmd = any(p in lower_cmd for p in ("volume up", "volume down", "mute volume", "mute audio", "unmute", "set volume", "increase volume", "decrease volume", "lower volume")) or (lower_cmd in ("mute", "unmute", "volume max"))
        if is_volume_cmd and not any(m in lower_cmd for m in ("phone", "mobile", "android", "tablet")):
            def _run_volume():
                from actions.computer_settings import volume_up, volume_down, volume_mute, volume_set
                import re
                if any(w in lower_cmd for w in ("up", "increase", "higher", "raise")):
                    volume_up()
                    self.speak("Volume increased.")
                elif any(w in lower_cmd for w in ("down", "decrease", "lower")):
                    volume_down()
                    self.speak("Volume decreased.")
                elif "unmute" in lower_cmd or "mute" in lower_cmd:
                    volume_mute()
                    self.speak("Audio toggled.")
                else:
                    m = re.search(r"(\d+)", lower_cmd)
                    if m:
                        val = int(m.group(1))
                        volume_set(val)
                        self.speak(f"Volume set to {val} percent.")
                    else:
                        volume_up()
                        self.speak("Volume adjusted.")
            threading.Thread(target=_run_volume, daemon=True).start()
            return

        # Local PC App Launcher (runs on computer unless explicitly targeted to phone)
        has_mobile_target = any(m in lower_cmd for m in ("on phone", "on my phone", "on mobile", "on my mobile", "on android", "on tablet"))
        is_open_app_cmd = any(lower_cmd.startswith(prefix) for prefix in ("open app ", "open ", "launch app ", "launch ", "start app ", "start ")) and not has_mobile_target and not any(p in lower_cmd for p in ("website", "url", "http", "presentation", "sheet", "spreadsheet", "project", "code", "game"))
        if is_open_app_cmd:
            from actions.open_app import open_app, _APP_ALIASES
            clean_app_candidate = lower_cmd
            for prefix in ("open app ", "open ", "launch app ", "launch ", "start app ", "start "):
                if clean_app_candidate.startswith(prefix):
                    clean_app_candidate = clean_app_candidate[len(prefix):].strip()
                    break
            if clean_app_candidate in _APP_ALIASES or any(clean_app_candidate in k for k in _APP_ALIASES):
                def _run_open_local_app():
                    open_app({"app_name": clean_app_candidate}, player=self.ui)
                    self.speak(f"Opening {clean_app_candidate}, sir.")
                threading.Thread(target=_run_open_local_app, daemon=True).start()
                return

        memory_ctx = _memory_context_for_request(text)
        routed_text = f"{memory_ctx}\n\nCurrent User Request:\n{text}" if memory_ctx else text
        if source == "instagram":
            routed_text = f"Owner sent this via Instagram DM: {text}\n(SYSTEM: If this is an action like opening an app or running a command, you MUST execute it using your tools rather than just replying with text.)"
        if text.lower() in {"stop meeting mode", "end meeting mode", "close meeting mode"}:
            self._stop_meeting_mode("Meeting mode closed.")
            return
        if self._handle_attention_response(text):
            return
        try:
            self.ui.begin_task_workspace(text, _build_task_plan(text), source=source or "local")
        except Exception:
            pass
        if source != "instagram" and self._handle_nexus_connect_command(text, source=source or "local"):
            return
        if self._handle_smart_home_command(text, source=source or "local"):
            return
        is_cam_req = _looks_like_camera_request(text)
        is_scr_req = _looks_like_screen_request(text)
        if is_cam_req or is_scr_req:
            vision_angle = "camera" if is_cam_req else "screen"
            title_text = "Webcam Inspection" if is_cam_req else "Screen Analysis"
            status_text = "Checking camera..." if is_cam_req else "Scanning screen..."
            output_text = "Nexus Core is inspecting your camera..." if is_cam_req else "Nexus Core is inspecting the screen for what you asked about."
            try:
                self.ui.update_task_workspace(
                    title=title_text,
                    status=status_text,
                    output=output_text,
                    percent=40,
                )
            except Exception:
                pass
            print(f"[Main] {title_text} request received")
            img_bytes = None
            if vision_angle == "screen" and hasattr(self.ui, "capture_screen_bytes"):
                print("[Main] Capturing screenshot from UI")
                img_bytes = self.ui.capture_screen_bytes()
                print(f"[Main] UI screenshot capture returned {len(img_bytes) if img_bytes is not None else 'None'} bytes")

            def _run_screen_process():
                print("[Main] Starting vision_process thread")
                success = screen_process(
                    parameters={"angle": vision_angle, "text": text},
                    response=None,
                    player=self.ui,
                    session_memory=None,
                    image_bytes=img_bytes,
                )
                print(f"[Main] vision_process finished: {success}")
                if not success:
                    try:
                        self.ui.update_task_workspace(
                            status=f"{title_text} failed",
                            output=(
                                "Visual perception could not complete. "
                                "Check your internet connection, API key, or camera/screen permissions."
                            ),
                            percent=0,
                        )
                    except Exception:
                        pass

            threading.Thread(target=_run_screen_process, daemon=True).start()
            return
        # Route to preferred provider: Google Gemini, OpenRouter, or Local Brain
        app_settings = config_manager.load_settings()
        configured_provider = app_settings.get("default_ai_provider", "Gemini")
        is_offline_mode = bool(app_settings.get("offline_mode_enabled", False))
        is_cloud_gemini = configured_provider in ("Gemini", "Google Gemini")

        # If Gemini Live session is connected and user selected Gemini, route text directly through Live duplex
        if is_cloud_gemini and self.session and self._loop and not is_offline_mode:
            import asyncio
            async def _send_live_text():
                try:
                    content = types.Content(role="user", parts=[types.Part.from_text(text=text)])
                    await self.session.send_client_content(turns=[content], turn_complete=True)
                except Exception as exc:
                    print(f"[NEXUS CORE] Live stream turn error, falling back: {exc}")
                    threading.Thread(target=self._fallback_reply, args=(text, memory_ctx), daemon=True).start()
            asyncio.run_coroutine_threadsafe(_send_live_text(), self._loop)
            return

        # Cascade (OpenRouter / Local Brain / REST) when Gemini Live is not preferred, disconnected, or in offline mode
        threading.Thread(target=self._fallback_reply, args=(text, memory_ctx), daemon=True).start()
        return


    def _handle_smart_home_command(self, text: str, source: str = "local") -> bool:
        normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s%]", " ", text.lower())).strip()
        
        # Don't touch commands targeted at phone or mobile
        mobile_words = (
            "phone", "mobile", "android", "tablet", "nexus connect",
            "my phone", "my mobile", "my tablet", "my android", "flashlight", "torch"
        )
        if any(word in normalized for word in mobile_words):
            return False

        # Don't hijack PC screen/monitor brightness
        if any(w in normalized for w in ("screen", "monitor", "display", "laptop", "pc")) and "brightness" in normalized:
            return False

        # Check for registered smart home devices
        devices = []
        try:
            devices = self._smart_home.list_devices() or []
        except Exception:
            devices = []

        is_explicit_brand = bool(re.search(r"\b(smart\s*home|kasa|atomberg|tplink|tp-link)\b", normalized))
        matched_device = False
        for d in devices:
            d_name = str(d.get("name", "")).lower()
            d_room = str(d.get("room", "")).lower()
            if d_name and re.search(rf"\b{re.escape(d_name)}\b", normalized):
                matched_device = True
                break
            if d_room and re.search(rf"\b{re.escape(d_room)}\b", normalized):
                matched_device = True
                break

        has_appliance = bool(re.search(r"\b(fan|fans|light|lights|lamp|plug|socket|outlet|bulb|air\s*conditioner|thermostat|ac)\b", normalized))
        has_control_action = bool(re.search(r"\b(turn\s+(?:on|off)|switch\s+(?:on|off)|power\s+(?:on|off)|toggle|dim|brighten|speed\s+up|slow\s+down|set\s+(?:temperature|speed|brightness))\b", normalized))

        # Only intercept if:
        # 1. Explicit brand mentioned, OR
        # 2. Known device name matched, OR
        # 3. Known appliance word matched WITH an explicit control action
        if not (is_explicit_brand or (has_appliance and has_control_action) or (matched_device and has_control_action)):
            return False

        if not devices and not is_explicit_brand:
            return False

        try:
            result = self._smart_home.execute_command(text)
            if not result or not result.get("success", True):
                return False
            detail = str(result.get("detail") or "Smart-home command completed.")
            title = f"Smart Home: {result.get('action', 'control')}"
            plan = [
                "Identify the target device or room",
                "Send the command to the smart-home provider",
                "Verify the new state",
                "Report the result",
            ]
            self.ui.update_task_workspace(
                title=title,
                command=text,
                plan=plan,
                status="Executing smart-home command",
                output=detail,
                percent=100,
                source=source,
            )
            self.ui.write_log(f"Nexus Core: {detail}")
            self.speak(detail)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return True
        except Exception as exc:
            self.ui.write_log(f"WARN: Smart-home execution bypassed: {exc}")
            return False

    def _extract_launch_app_name(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s%]", " ", text.lower())).strip()
        if not normalized:
            return ""

        prefixes = (
            "launch app ",
            "open app ",
            "start app ",
            "open the app ",
            "launch the app ",
            "start the app ",
            "open ",
            "launch ",
            "start ",
            "run ",
            "bring up ",
        )

        candidate = normalized
        for prefix in prefixes:
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):]
                break

        candidate = re.sub(r"\s+(?:on|in|to)\s+(?:my\s+)?(?:phone|mobile|tablet|android|device)\b.*$", "", candidate).strip()
        candidate = re.sub(r"\b(?:app|application|please|the)\b", " ", candidate).strip()
        candidate = re.sub(r"\s+", " ", candidate)
        return candidate

    def _handle_nexus_connect_command(self, text: str, source: str = "local", parsed_intent: Any = None) -> bool:
        normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s%]", " ", text.lower())).strip()
        
        action = None
        params: dict[str, object] = {}

        if parsed_intent and getattr(parsed_intent, "intent", "") == "mobile_connect":
            action = parsed_intent.action
            params = dict(getattr(parsed_intent, "parameters", {}) or {})
            has_phone_ref = True
            is_flashlight = "flashlight" in action
            is_ring_phone = "ring" in action
        else:
            # Explicit mobile indicators: only route to phone if user explicitly mentions phone/mobile
            # or asks for a phone-exclusive action (flashlight/torch, ring phone).
            is_flashlight = "flashlight" in normalized or "torch" in normalized
            is_ring_phone = any(p in normalized for p in ("ring phone", "ring my phone", "find my phone", "find phone", "locate phone"))
            has_phone_ref = any(token in normalized for token in (
                "phone", "mobile", "android", "tablet", "nexus connect",
                "my phone", "my mobile", "my tablet", "my android"
            ))

            # Never hijack local PC commands (e.g. open chrome, volume up, pc battery) unless user says 'on phone'
            if not (has_phone_ref or is_flashlight or is_ring_phone):
                return False

            # Check for complex multi-step mobile workflow first
            # Examples: "open X and do Y", "search for Z on X", "message X on Y"
            if (" and " in normalized or " search " in normalized or " play " in normalized or " message " in normalized or " tell " in normalized) and ("open " in normalized or "launch " in normalized or "app" in normalized):
                action = "mobile_autopilot"
                params["instruction"] = text
            elif is_ring_phone:
                action = "ring_phone"
            elif "flashlight" in normalized and ("turn on" in normalized or "switch on" in normalized or "power on" in normalized or "on" in normalized):
                action = "flashlight_on"
            elif "flashlight" in normalized and ("turn off" in normalized or "switch off" in normalized or "power off" in normalized or "off" in normalized):
                action = "flashlight_off"
            elif "battery" in normalized or "charge" in normalized:
                action = "get_battery"
            elif "open url" in normalized or "open website" in normalized or "go to" in normalized:
                action = "open_url"
            elif any(word in normalized for word in ("launch app", "open app", "start app", "open ", "launch ", "start ", "run ", "bring up ")):
                app_name = self._extract_launch_app_name(text)
                if app_name:
                    action = "launch_app"
                    params["app_name"] = app_name
            elif "volume" in normalized and ("set" in normalized or "change" in normalized or "to " in normalized):
                action = "volume_set"
                match = re.search(r"\b(\d{1,3})\b", normalized)
                if match:
                    params["value"] = int(match.group(1))
            elif "volume" in normalized:
                action = "volume_get"
            elif "info" in normalized or "status" in normalized:
                action = "get_device_info"
                
            if not action:
                return False

        try:
            devices_json = connect_list_devices(parameters={}, player=self.ui)
            devices = json.loads(devices_json).get("devices", [])
        except Exception:
            devices = []

        if not devices:
            msg = "No phone is currently connected to Nexus. Please pair or connect your phone via Nexus Connect or the Mobile Connect dashboard, sir."
            try:
                self.ui.update_task_workspace(
                    title=f"Nexus Connect: {action}",
                    command=text,
                    plan=["Search for paired devices", "Verify mobile connection"],
                    status="No Device Connected",
                    output=msg,
                    percent=0,
                    source=source,
                )
            except Exception:
                pass
            self.ui.write_log(f"[Nexus Connect] {msg}")
            self.speak(msg)
            return True

        try:
            target = ""
            for device in devices:
                name = str(device.get("name", "")).lower()
                device_id = str(device.get("device_id", "")).lower()
                platform = str(device.get("platform", "")).lower()
                if any(token in normalized for token in (name, device_id, platform, "phone", "mobile", "android", "tablet")):
                    target = str(device.get("device_id") or device.get("name") or "").strip()
                    break
            if not target and (has_phone_ref or is_flashlight or is_ring_phone) and len(devices) == 1:
                target = str(devices[0].get("device_id") or devices[0].get("name") or "").strip()
            if not target and devices:
                target = str(devices[0].get("device_id") or devices[0].get("name") or "").strip()
            if not target:
                return False

            if action == "mobile_autopilot":
                # Route complex commands to the autopilot loop
                def _run_autopilot():
                    try:
                        from actions.mobile_autopilot import mobile_autopilot
                        result_json = mobile_autopilot({"target": target, "instruction": params["instruction"]}, player=self.ui, speak=self.speak)
                        print(f"[Autopilot Result]: {result_json}")
                        try:
                            result_dict = json.loads(result_json)
                            if not result_dict.get("success"):
                                print(f"[Autopilot Error]: {result_dict.get('error') or result_dict}")
                                self.speak(f"Autopilot encountered an error: {result_dict.get('error', 'unknown error')}")
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"Autopilot failed: {e}")
                    finally:
                        try:
                            self.ui.set_state("IDLE")
                        except Exception:
                            pass
                threading.Thread(target=_run_autopilot, daemon=True).start()
                return True

            if action == "launch_app":
                app_name = str(params.get("app_name") or "").strip()
                if not app_name:
                    return False
            if action == "open_url":
                m = re.search(r"(https?://\S+)", text, re.IGNORECASE)
                if m:
                    params["url"] = m.group(1)
                else:
                    return False

            payload = {
                "device": target,
                "action": action,
                "parameters": params,
            }
            result_json = connect_execute(parameters=payload, player=self.ui)
            result = json.loads(result_json)
            if result.get("success", False):
                detail = str(result.get("detail") or result.get("message") or "")
                if not detail:
                    if action == "launch_app":
                        detail = f"Opening {params.get('app_name')} on your phone, sir."
                    elif action == "flashlight_on":
                        detail = "Flashlight turned on."
                    elif action == "flashlight_off":
                        detail = "Flashlight turned off."
                    elif action == "ring_phone":
                        detail = "Ringing your phone now, sir."
                    else:
                        detail = "Device command completed."
                title = f"Nexus Connect: {action}"
                self.ui.update_task_workspace(
                    title=title,
                    command=text,
                    plan=[
                        "Identify the paired phone or device",
                        "Route the command through Nexus Connect",
                        "Verify the device response",
                        "Report the result",
                    ],
                    status="Executing device command",
                    output=detail,
                    percent=100,
                    source=source,
                )
                self.ui.write_log(f"Nexus Core: {detail}")
                self.speak(detail)
                if not self.ui.muted:
                    self.ui.set_state("LISTENING")
                return True

            error_msg = str(result.get("error") or "Device command failed.")
            self.ui.write_log(f"ERR: Nexus Connect command failed: {error_msg}")
            self.speak(f"Could not complete action on your phone: {error_msg}")
            try:
                self.ui.update_task_workspace(
                    title=f"Nexus Connect: {action}",
                    command=text,
                    plan=["Route command to phone", "Execute action"],
                    status="Execution Failed",
                    output=error_msg,
                    percent=0,
                    source=source,
                )
            except Exception:
                pass
            return True
        except Exception as exc:
            self.ui.write_log(f"ERR: Nexus Connect exception: {exc}")
            return False

    def _connect_tool_voice(self, name: str, raw_result: str) -> str | None:
        if not str(name or "").startswith("connect_"):
            return None
        try:
            data = json.loads(raw_result) if isinstance(raw_result, str) else dict(raw_result or {})
        except Exception:
            data = {}

        if name == "connect_list_devices":
            count = int(data.get("count") or len(data.get("devices") or []))
            return f"I found {count} connected device{'s' if count != 1 else ''}."

        if name == "connect_get_device":
            device = data.get("device") or {}
            label = str(device.get("name") or "the device")
            status = "online" if device.get("online") else "offline"
            return f"{label} is {status}."

        if name == "connect_get_capabilities":
            device = data.get("device") or {}
            label = str(device.get("name") or "The device")
            return f"{label} capabilities are ready."

        if name == "connect_pair_device":
            pairing = data.get("pairing") or data
            code = str(pairing.get("pairing_code") or "").strip()
            if code:
                return f"Pairing code ready: {code}."
            return "Pairing is ready."

        if name == "connect_disconnect_device":
            return "The device has been disconnected."

        if name == "connect_execute":
            if data.get("success", False):
                detail = data.get("detail")
                if isinstance(detail, dict):
                    detail = detail.get("message") or detail.get("status") or detail.get("result")
                if not detail and isinstance(data.get("data"), dict):
                    payload = data.get("data") or {}
                    detail = payload.get("message") or payload.get("status") or payload.get("result")
                if not detail:
                    detail = data.get("error") or "Task completed."
                return str(detail)
            return str(data.get("error") or "The device command failed.")

        return None

    def _attention_message(self, event: dict) -> str:
        app = (event.get("app") or "an app").strip()
        kind = (event.get("kind") or "message").strip().lower()
        if kind == "call":
            return f"Incoming call detected on {app}. Should I pick it up, ignore it, or cut the call?"
        title = (event.get("title") or "").strip()
        preview = (event.get("preview") or "").strip()
        if title:
            return f"You received a message on {app} from {title}. It says: {preview}"
        return f"You received a message on {app}. It says: {preview}"

    def _announce_attention(self, event: dict):
        msg = self._attention_message(event)
        self.ui.write_log(f"Nexus Core: {msg}")
        if self.session and self._loop:
            self.speak(msg)
        else:
            threading.Thread(target=speak_native, args=(msg,), daemon=True).start()
        self.ui.show_attention_alert(event)

    def _on_external_notification(self, event: dict):
        if not isinstance(event, dict):
            return
        kind = (event.get("kind") or "message").strip().lower()
        app = (event.get("app") or "App").strip()
        preview = (event.get("preview") or "").strip()
        settings = {}
        try:
            settings = self.ui._load_app_settings()
        except Exception:
            settings = {}

        if kind == "call" and not bool(settings.get("attention_call_prompts", True)):
            return
        if kind == "message" and not bool(settings.get("attention_message_prompts", True)):
            return

        with self._attention_lock:
            current = self._pending_attention
            if current:
                same_app = (current.get("app") or "").strip().lower() == app.lower()
                same_kind = (current.get("kind") or "").strip().lower() == kind
                if same_app and same_kind:
                    return
            self._pending_attention = dict(event)

        self._announce_attention(event)
        if preview:
            self.ui.write_log(f"[Attention] {app}: {preview}")
        if kind == "call" and app.lower() in {"zoom", "teams", "whatsapp"}:
            self._start_meeting_mode(event)

    def _start_meeting_mode(self, event: dict | str | None = None):
        if isinstance(event, str):
            event = {"app": "Meeting", "title": event}
        event = dict(event or {})
        app = (event.get("app") or "Meeting").strip()
        title = event.get("title") or f"{app} meeting"
        summary = f"Watching {app} for questions and answers."
        with self._meeting_lock:
            self._meeting_active = True
            self._meeting_event = event
        self.ui.set_meeting_mode(True, title, summary, "Listening for questions on screen...", self._meeting_assistant.latest_speech())
        self._meeting_assistant.start(title=title, context=summary)
        self.ui.write_log(f"SYS: Meeting mode enabled for {app}.")

    def _stop_meeting_mode(self, reason: str = "Meeting mode stopped."):
        with self._meeting_lock:
            was_active = self._meeting_active
            self._meeting_active = False
            self._meeting_event = None
        if was_active:
            self._meeting_assistant.stop()
            self.ui.set_meeting_mode(False, "", "", "")
            self.ui.write_log(f"SYS: {reason}")

    def _on_meeting_update(self, payload: dict):
        if not isinstance(payload, dict):
            return
        active = bool(payload.get("active"))
        title = payload.get("title") or "Meeting mode"
        summary = payload.get("summary") or ""
        answer = payload.get("answer") or ""
        speech = payload.get("speech") or ""
        self.ui.set_meeting_mode(active, title, summary, answer, speech)
        if summary:
            self.ui.write_log(f"[Meeting] {summary}")
        if answer:
            self.ui.write_log(f"Nexus Core: {answer}")

    def _on_meeting_state(self, state: str):
        if state == "LISTENING":
            self.ui.set_state("LISTENING")
        elif state == "MEETING":
            self.ui.set_state("THINKING")

    def _attention_matches(self, text: str, words: tuple[str, ...]) -> bool:
        t = (text or "").lower()
        return any(word in t for word in words)

    def _prompt_message_reply(self, event: dict) -> bool:
        if not isinstance(event, dict):
            return False
        with self._attention_lock:
            self._pending_reply_event = dict(event)
            self._pending_attention = None
            self._reply_mode = True

        message = "What would you like to say in reply?"
        self.ui.write_log(f"Nexus Core: {message}")
        if self.session and self._loop:
            self.speak(message)
        else:
            threading.Thread(target=speak_native, args=(message,), daemon=True).start()
        try:
            self.ui.begin_task_workspace(
                "Replying to message",
                [
                    "Type your response",
                    "I will reword it naturally",
                    f"Send via {event.get('app', 'the app')}",
                ],
                source="reply",
            )
            self.ui.update_task_workspace(
                status="Awaiting your reply",
                output="Type the message you want to send, and I will make it sound natural before sending it as you.",
                percent=10,
            )
        except Exception:
            pass
        return True

    def _handle_pending_reply(self, text: str) -> bool:
        with self._attention_lock:
            event = dict(self._pending_reply_event or {})
            self._pending_reply_event = None
        if not event:
            return False

        lower = (text or "").lower()
        if self._attention_matches(lower, ("cancel", "never mind", "skip", "do not send", "don't send")):
            self._reply_mode = False
            self.ui.write_log("SYS: Reply cancelled.")
            try:
                self.ui.finish_task_workspace("Reply cancelled.", "Cancelled", 100)
            except Exception:
                pass
            return True

        self.ui.write_log(f"SYS: Drafting reply to {event.get('title') or event.get('app')}.")
        threading.Thread(target=self._draft_and_send_reply, args=(event, text), daemon=True).start()
        return True

    def _rewrite_reply_text(self, user_text: str, event: dict) -> str:
        prompt = (
            "You are a friendly assistant helping a user rewrite their draft reply for a chat message. "
            "Keep the same meaning and intent, expand the wording slightly, and make it sound natural and human. "
            "Do not mention the notification, app, or any internal system details. "
            "Return only the rewritten reply text.\n\n"
            "Notification context:\n"
            f"App: {event.get('app', '')}\n"
            f"Sender: {event.get('title', '')}\n"
            f"Preview: {event.get('preview', '')}\n\n"
            "User draft reply:\n"
            f"{user_text}\n\n"
            "Reply text:"
        )
        try:
            return _gemini_text_reply(prompt) or user_text
        except Exception:
            try:
                return openrouter_client.chat(
                    prompt,
                    system="You are a friendly assistant. Rewrite the reply naturally and humanely.",
                )
            except Exception:
                return user_text

    def _draft_and_send_reply(self, event: dict, text: str):
        try:
            reply_text = self._rewrite_reply_text(text, event)
            if not reply_text:
                reply_text = text
            self.ui.update_task_workspace(
                status="Sending reply",
                output="Sending your expanded reply now...",
                percent=70,
            )
            receiver = (event.get("title") or "").strip()
            platform = (event.get("app") or "whatsapp").strip()
            if not receiver:
                self.ui.write_log("ERR: Could not determine recipient for reply.")
                try:
                    self.ui.finish_task_workspace("Reply failed: recipient not found.", "Reply failed", 100)
                except Exception:
                    pass
                return
            result = send_message(
                parameters={
                    "receiver": receiver,
                    "message_text": reply_text,
                    "platform": platform,
                },
                player=self.ui,
            )
            self._reply_mode = False
            self.ui.write_log(f"SYS: {result}")
            try:
                self.ui.finish_task_workspace(reply_text, "Reply delivered.", 100)
            except Exception:
                pass
        except Exception as e:
            self._reply_mode = False
            self.ui.write_log(f"ERR: Reply failed: {e}")
            try:
                self.ui.finish_task_workspace(f"Reply failed: {e}", "Reply failed", 100)
            except Exception:
                pass
        finally:
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

    def _parse_ig_reply_intent(self, text: str) -> tuple[str, str]:
        system_prompt = (
            "You are an intent parser. The user received an Instagram DM. I asked: 'What should I reply, or should I take over?'. "
            "The user responded. Determine their intent.\n"
            "1. If they want me to take over/handle it, return TAKE_OVER.\n"
            "2. If they want to cancel/skip, return CANCEL.\n"
            "3. If they dictate a specific message to send (e.g. 'tell them I am busy', 'say hi'), return MANUAL_REPLY and the exact text.\n"
            "4. If they are just greeting me (e.g. 'hi') or making small talk, return IGNORE.\n"
            "Output ONLY valid JSON: {\"intent\": \"...\", \"reply_text\": \"...\"}"
        )
        try:
            client = genai.Client(api_key=_get_api_key(), http_options={"api_version": "v1beta"})
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=f"{system_prompt}\n\nUser Response: {text}",
                config={"temperature": 0.1, "response_mime_type": "application/json"}
            )
            data = json.loads(response.text.strip())
            return data.get("intent", "IGNORE"), data.get("reply_text", "")
        except Exception:
            lower = text.lower()
            if any(c in lower for c in ("cancel", "stop", "skip", "never mind", "abort", "don't reply", "do not reply")):
                return "CANCEL", ""
            if any(a in lower for a in ("take over", "auto mode", "handle it", "you reply", "auto reply", "take care of it")):
                return "TAKE_OVER", ""
            for verb in ("reply", "tell him", "tell her", "tell them", "tell", "say", "send"):
                if verb in lower:
                    import re
                    pattern = rf"^.*?\b{verb}\b(?:\s+(?:him|her|them|that|to\s+say|saying))?\s*"
                    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
                    if cleaned:
                        return "MANUAL_REPLY", cleaned
            if len(text.strip().split()) >= 2 and not any(g in lower for g in ("hello", "hey brahma", "who are you")):
                return "MANUAL_REPLY", text.strip()
            return "IGNORE", ""

    def _handle_ig_reply_flow(self, text: str) -> bool:
        if getattr(self, "_ig_pending_thread", None):
            thread_id = self._ig_pending_thread.get("thread_id")
            username = self._ig_pending_thread.get("username")
            message_text = self._ig_pending_thread.get('message')
            
            intent, payload = self._parse_ig_reply_intent(text)
            
            if intent == "CANCEL":
                self._ig_reply_mode = False
                msg = "Instagram reply cancelled."
                self.ui.write_log(f"Nexus Core: {msg}")
                self.speak(msg)
                self._ig_pending_thread = None
                return True
                
            if intent == "TAKE_OVER":
                self.ui.write_log("SYS: Taking over Instagram thread.")
                self.speak(f"I will now take over the chat with {username}.")
                from actions.instagram_mcp import add_auto_thread, send_direct_reply
                add_auto_thread(thread_id)
                def _generate_and_send():
                    try:
                        reply = _ig_gemini_reply(username, message_text)
                        send_direct_reply(thread_id, reply)
                    except Exception as e:
                        print(f"Error taking over thread: {e}")
                threading.Thread(target=_generate_and_send, daemon=True).start()
                
            elif intent == "MANUAL_REPLY":
                self.ui.write_log(f"SYS: Sending manual reply to @{username}: '{payload}'")
                self.speak("Message sent.")
                from actions.instagram_mcp import send_direct_reply
                def _do_send():
                    try:
                        send_direct_reply(thread_id, payload)
                    except Exception as e:
                        print(f"Error sending manual reply to @{username}: {e}")
                threading.Thread(target=_do_send, daemon=True).start()
                
            elif intent == "IGNORE":
                return False
                
            self._ig_reply_mode = False
            self._ig_pending_thread = None
            return True
        return False

    def _handle_email_flow(self, text: str) -> bool:
        lower = text.lower()
        if any(cancel in lower for cancel in ("cancel", "never mind", "skip", "stop", "abort")):
            self._email_mode = False
            self._email_step = 0
            self._email_profiles = {}
            msg = "Email sending cancelled, sir."
            self.ui.write_log(f"Nexus Core: {msg}")
            self.speak(msg)
            try:
                self.ui.finish_task_workspace("Email sending cancelled.", "Cancelled", 100)
            except Exception:
                pass
            return True

        if self._email_step == 0:
            # We just collected the recipient
            self._email_recipient = text.strip()
            self._email_step = 1
            prompt = "Which email app would you like to use? (Gmail, default mail app, etc.)"
            self.ui.write_log(f"Nexus Core: {prompt}")
            self.speak(prompt)
            try:
                self.ui.update_task_workspace(
                    status="Selecting email app",
                    output=f"Recipient: {self._email_recipient}. Asking for email application...",
                    percent=40,
                )
            except Exception:
                pass
            return True

        elif self._email_step == 1:
            # We just collected the app name
            self._email_app = text.strip()
            self._email_step = 2
            
            prompt = "What is the message you'd like to send?"
            self.ui.write_log(f"Nexus Core: {prompt}")
            self.speak(prompt)
            try:
                self.ui.update_task_workspace(
                    status="Collecting message",
                    output=f"Recipient: {self._email_recipient} | App: {self._email_app}. Asking for message content...",
                    percent=70,
                )
            except Exception:
                pass
            return True

        elif self._email_step == 2:
            # We just collected the message
            self._email_message = text.strip()
            self._email_mode = False
            self._email_step = 0
            
            # Now let's execute composing!
            msg = f"Opening {self._email_app} and composing email to {self._email_recipient}..."
            self.ui.write_log(f"Nexus Core: {msg}")
            self.speak(msg)
            try:
                self.ui.update_task_workspace(
                    status="Composing email",
                    output=f"Composing message to {self._email_recipient} via {self._email_app}...",
                    percent=90,
                )
            except Exception:
                pass
            
            try:
                import urllib.parse
                import webbrowser
                subject = "Message from Nexus Core"
                quoted_recipient = urllib.parse.quote(self._email_recipient)
                quoted_subject = urllib.parse.quote(subject)
                quoted_body = urllib.parse.quote(self._email_message)
                
                import os
                import subprocess
                import shutil

                app_lower = self._email_app.lower()
                chrome_opened = False

                if "gmail" in app_lower or "chrome" in app_lower:
                    import urllib.parse
                    quoted_recipient = urllib.parse.quote(self._email_recipient)
                    quoted_subject = urllib.parse.quote("Message from Nexus Core")
                    quoted_body = urllib.parse.quote(self._email_message)
                    url = f"https://mail.google.com/mail/?view=cm&fs=1&to={quoted_recipient}&su={quoted_subject}&body={quoted_body}"
                    
                    # Use webbrowser to naturally open a new tab in the already running Chrome window
                    import webbrowser
                    webbrowser.open(url)

                elif "outlook" in app_lower:
                    url = f"https://outlook.live.com/default/?path=/mail/action/compose&to={quoted_recipient}&subject={quoted_subject}&body={quoted_body}"
                    webbrowser.open(url)
                else:
                    url = f"mailto:{quoted_recipient}?subject={quoted_subject}&body={quoted_body}"
                    webbrowser.open(url)
                
                try:
                    self.ui.finish_task_workspace("Email composed successfully.", "Composed", 100)
                except Exception:
                    pass
            except Exception as e:
                err_msg = f"Failed to compose email: {e}"
                self.ui.write_log(f"ERR: {err_msg}")
                self.speak(err_msg)
                try:
                    self.ui.finish_task_workspace(err_msg, "Failed", 100)
                except Exception:
                    pass
            return True

        return False

    def _handle_attention_response(self, text: str) -> bool:
        with self._attention_lock:
            event = dict(self._pending_attention or {})
        if not event:
            return False

        kind = (event.get("kind") or "message").strip().lower()
        lower = (text or "").lower()

        if kind == "message":
            if self._attention_matches(lower, ("reply", "respond", "answer", "write back", "send reply", "send a reply")):
                return self._prompt_message_reply(event)
            if self._attention_matches(lower, ("hear", "read", "what is it", "tell me", "show it", "open it")):
                preview = read_event_preview(event)
                self.ui.write_log(f"Nexus Core: {preview}")
                threading.Thread(target=speak_native, args=(preview,), daemon=True).start()
                with self._attention_lock:
                    self._pending_attention = None
                return True
            if self._attention_matches(lower, ("ignore", "dismiss", "skip", "no", "not now")):
                self.ui.write_log("SYS: Message alert dismissed.")
                with self._attention_lock:
                    self._pending_attention = None
                return True
            return False

        if kind == "call":
            if self._attention_matches(lower, ("pick up", "answer", "accept", "take it", "join")):
                result = handle_call_action(event, "accept")
                self.ui.write_log(f"SYS: {result}")
                threading.Thread(target=speak_native, args=(result,), daemon=True).start()
                with self._attention_lock:
                    self._pending_attention = None
                return True
            if self._attention_matches(lower, ("ignore", "decline", "reject", "cut", "hang up", "end")):
                result = handle_call_action(event, "decline")
                self.ui.write_log(f"SYS: {result}")
                threading.Thread(target=speak_native, args=(result,), daemon=True).start()
                with self._attention_lock:
                    self._pending_attention = None
                return True
            if self._attention_matches(lower, ("x", "nothing", "do nothing", "close")):
                self.ui.write_log("SYS: Call alert dismissed.")
                with self._attention_lock:
                    self._pending_attention = None
                return True
            return False

        return False

    def _on_attention_action(self, event: dict, decision: str):
        if not isinstance(event, dict):
            return
        kind = (event.get("kind") or "message").strip().lower()
        decision = (decision or "").strip().lower()

        if kind == "meeting":
            if decision == "stop":
                self._stop_meeting_mode()
            return

        if kind == "message":
            if decision == "hear":
                preview = read_event_preview(event)
                self.ui.write_log(f"Nexus Core: {preview}")
                threading.Thread(target=speak_native, args=(preview,), daemon=True).start()
            elif decision == "reply":
                self._prompt_message_reply(event)
                return
            else:
                self.ui.write_log("SYS: Message alert dismissed.")
            with self._attention_lock:
                self._pending_attention = None
            return

        if kind == "call":
            if decision in {"accept", "answer", "pick_up"}:
                result = handle_call_action(event, "accept")
                self.ui.write_log(f"SYS: {result}")
                threading.Thread(target=speak_native, args=(result,), daemon=True).start()
            elif decision in {"noop", "x", "none"}:
                self.ui.write_log("SYS: Call alert dismissed.")
            else:
                result = handle_call_action(event, "decline")
                self.ui.write_log(f"SYS: {result}")
                threading.Thread(target=speak_native, args=(result,), daemon=True).start()
            with self._attention_lock:
                self._pending_attention = None


    def _execute_tool_sync(self, name: str, args: dict, call_id: str = "call_local") -> str:
        class LocalFC:
            def __init__(self, n, a, cid):
                self.name = n
                self.args = a
                self.id = cid
                self.silent_completion = True

        fc = LocalFC(name, args, call_id)
        if self._loop and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self._execute_tool(fc), self._loop)
                fr = future.result(timeout=60)
                res_obj = getattr(fr, "response", {})
                return res_obj.get("result", str(res_obj))
            except Exception as e:
                return f"Tool execution failed: {e}"
        else:
            try:
                fr = asyncio.run(self._execute_tool(fc))
                res_obj = getattr(fr, "response", {})
                return res_obj.get("result", str(res_obj))
            except Exception as e:
                return f"Tool execution failed: {e}"

    def _fallback_reply(self, text: str, memory_ctx: str = ""):
        try:
            self.ui.set_state("THINKING")
            try:
                self.ui.update_task_workspace(
                    status="Thinking",
                    output="Nexus Core is drafting a direct reply.",
                    percent=35,
                )
            except Exception:
                pass
            reply = ""
            gemini_first = not self._use_openrouter_first
            request_text = f"{memory_ctx}\n\nCurrent User Request:\n{text}" if memory_ctx else text

            app_settings = config_manager.load_settings()
            configured_provider = app_settings.get("default_ai_provider", "Gemini")
            local_model_target = app_settings.get("local_ai_model", "qwen2.5:3b")
            is_offline_mode = app_settings.get("offline_mode_enabled", False)

            is_cloud_gemini = configured_provider in ("Gemini", "Google Gemini")
            is_cloud_openrouter = configured_provider == "OpenRouter"

            # 1. If user explicitly selected Google Gemini, run Gemini FIRST
            if is_cloud_gemini and not is_offline_mode:
                try:
                    self.ui.update_task_workspace(
                        status="Thinking (Gemini)",
                        output="Processing on Google Gemini...",
                        percent=50,
                    )
                    reply = _gemini_text_reply(request_text)
                    print("[NEXUS CORE] 🌐 Google Gemini answered successfully!")
                except Exception as e_gem:
                    print(f"[NEXUS CORE] ⚠️ Gemini failed: {e_gem}")
                    if _is_gemini_limit_error(e_gem):
                        self._use_openrouter_first = True

            # 2. If user explicitly selected OpenRouter, run OpenRouter FIRST
            elif is_cloud_openrouter and not is_offline_mode:
                try:
                    self.ui.update_task_workspace(
                        status="Thinking (OpenRouter)",
                        output="Processing on OpenRouter...",
                        percent=50,
                    )
                    reply = openrouter_client.chat(
                        request_text,
                        system=(
                            "You are Nexus Core, a concise, helpful desktop assistant. "
                            "Reply naturally and briefly. Do not mention internal implementation details."
                        ),
                    )
                    print("[NEXUS CORE] 🌐 OpenRouter answered successfully!")
                except PermissionError as e_key:
                    print(f"[NEXUS CORE] ⚠️ OpenRouter key error: {e_key}")
                    reply = "Sir, your OpenRouter API key is missing or invalid. Please configure your key in Settings."
                except Exception as e_or:
                    print(f"[NEXUS CORE] ⚠️ OpenRouter failed: {e_or}")
                    err_s = str(e_or)
                    if "API key is missing" in err_s or "401" in err_s:
                        reply = "Sir, please add your OpenRouter API key in Settings to use OpenRouter."
                    else:
                        reply = ""

            # 3. If user explicitly configured Local AI, is in Offline Mode, or cloud provider failed: run Local Brain
            if not reply and (configured_provider == "Local" or is_offline_mode or not (is_cloud_gemini or is_cloud_openrouter)) and local_brain.is_available():
                try:
                    self.ui.update_task_workspace(
                        status="Thinking (Local AI)",
                        output=f"Processing on local model ({local_model_target})...",
                        percent=50,
                    )
                    prompt_txt = ""
                    try:
                        if PROMPT_PATH.exists():
                            prompt_txt = PROMPT_PATH.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                    if not prompt_txt:
                        prompt_txt = "You are Nexus Core, the autonomous desktop operating system."

                    system_prompt = (
                        f"{prompt_txt}\n\n"
                        "CRITICAL OPERATING SYSTEM DIRECTIVE:\n"
                        "- You have FULL DIRECT ACCESS and authority over this Windows PC via your tools.\n"
                        "- NEVER state that you are a text-based AI, that you cannot perform automations, or that you lack real-time access.\n"
                        "- Whenever the user requests an action (opening an app, changing volume, setting a reminder, running a protocol, organizing files, searching, etc.), ALWAYS call the corresponding tool.\n"
                        "- Keep responses concise, direct, and conversational."
                    )

                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": request_text}
                    ]

                    res = local_brain.chat_complete(
                        messages,
                        model=local_model_target,
                        tools=TOOL_DECLARATIONS,
                        focus_core=True
                    )
                    msg = res.get("choices", [{}])[0].get("message", {})
                    tool_calls = msg.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            call_id = tc.get("id", "call_local")
                            fn_info = tc.get("function", {})
                            fn_name = fn_info.get("name")
                            fn_args_raw = fn_info.get("arguments", {})
                            if isinstance(fn_args_raw, str):
                                try:
                                    fn_args = json.loads(fn_args_raw)
                                except Exception:
                                    fn_args = {}
                            else:
                                fn_args = fn_args_raw or {}

                            print(f"[NEXUS CORE] 🔒 Local Brain executing tool: {fn_name}({fn_args})")
                            self.ui.update_task_workspace(
                                status=f"Executing {fn_name}",
                                output=f"Running action: {fn_name} on local machine...",
                                percent=75,
                            )
                            tool_result = self._execute_tool_sync(fn_name, fn_args, call_id)

                            messages.append(msg)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": fn_name,
                                "content": str(tool_result)
                            })
                            try:
                                followup_res = local_brain.chat_complete(
                                    messages,
                                    model=local_model_target,
                                    temperature=0.3
                                )
                                followup_reply = followup_res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                                if followup_reply:
                                    reply = followup_reply
                            except Exception as e_fu:
                                print(f"[NEXUS CORE] ⚠️ Local Brain follow-up failed: {e_fu}")
                                reply = str(tool_result) if tool_result else f"{fn_name.replace('_', ' ').capitalize()} completed."
                    else:
                        reply = msg.get("content", "").strip()
                    print(f"[NEXUS CORE] 🔒 Local Brain ({local_model_target}) answered successfully!")
                except Exception as e_loc:
                    print(f"[NEXUS CORE] ⚠️ Local Brain failed: {e_loc}")

            # 4. Fallback cascading: if primary cloud choice failed, try secondary cloud choice
            if not reply and not is_offline_mode:
                if is_cloud_gemini and self._use_openrouter_first:
                    try:
                        reply = openrouter_client.chat(request_text)
                    except Exception:
                        pass
                elif is_cloud_openrouter:
                    try:
                        reply = _gemini_text_reply(request_text)
                    except Exception:
                        pass

            # 4. Ultimate offline safety net: Local Brain fallback
            if not reply and local_brain.is_available():
                try:
                    res = local_brain.chat_complete([
                        {"role": "system", "content": "You are Nexus Core, the autonomous desktop operating system. You control this PC. Never claim you cannot do automations."},
                        {"role": "user", "content": request_text}
                    ], model=local_model_target, tools=TOOL_DECLARATIONS, focus_core=True)
                    msg_net = res.get("choices", [{}])[0].get("message", {})
                    tc_net = msg_net.get("tool_calls")
                    if tc_net:
                        call_id = tc_net[0].get("id", "call_local")
                        fn_name = tc_net[0].get("function", {}).get("name")
                        fn_args_raw = tc_net[0].get("function", {}).get("arguments", {})
                        if isinstance(fn_args_raw, str):
                            try:
                                fn_args = json.loads(fn_args_raw)
                            except Exception:
                                fn_args = {}
                        else:
                            fn_args = fn_args_raw or {}
                        reply = self._execute_tool_sync(fn_name, fn_args, call_id)
                    else:
                        reply = msg_net.get("content", "").strip()
                    print(f"[NEXUS CORE] 🔒 Local Brain offline safety net answered ({local_model_target})!")
                except Exception as e_net:
                    print(f"[NEXUS CORE] ⚠️ Offline Local Brain fallback failed: {e_net}")
            reply = (reply or "").strip()
            if not reply:
                if is_cloud_openrouter:
                    reply = "Sir, I couldn't reach OpenRouter right now. Please check your OpenRouter API key and internet connection."
                elif is_offline_mode or configured_provider == "Local":
                    reply = "I'm unable to reach the local AI engine. Please ensure Ollama is running."
                else:
                    reply = "I’m ready, sir."
            self.ui.write_log(f"Nexus Core: {reply}")
            # Only speak non-fallback replies; avoid looping on fallback
            is_fallback = reply in ("I’m ready, sir.", "I'm unable to reach the local AI engine. Please ensure Ollama is running.", "Sir, I couldn't reach OpenRouter right now. Please check your OpenRouter API key and internet connection.")
            if not getattr(self.ui, "muted", False) and not is_fallback:
                self.speak(reply, proactive=True)
            try:
                self.ui.finish_task_workspace(reply, "Reply delivered.", 100)
            except Exception:
                pass
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
        except Exception as e:
            msg = f"Fallback reply failed: {e}"
            print(f"[NEXUS CORE] ⚠️ {msg}")
            self.ui.write_log(f"ERR: {msg}")
            try:
                self.ui.finish_task_workspace(msg, "Reply failed.", 100)
            except Exception:
                pass
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            if self._is_speaking == value:
                return
            self._is_speaking = value
            now = time.monotonic()
            if value:
                self._spoke_start_time = now
            else:
                self._last_spoke_time = now
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def trigger_barge_in(self):
        """Immediately interrupts AI speech playback and switches state to LISTENING."""
        with self._speaking_lock:
            if not self._is_speaking and not getattr(self, "_server_turn_active", False):
                return
            self._is_speaking = False
            self._server_turn_active = False
            self._discard_server_audio = True
            self._last_spoke_time = time.monotonic()

        try:
            from actions.attention_monitor import stop_native_speech
            stop_native_speech()
        except Exception:
            pass

        try:
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except Exception:
                        break
        except Exception:
            pass

        try:
            from core.live_voice_engine import LiveVoiceEngine
            LiveVoiceEngine.get_instance().trigger_interruption(source="pc_barge_in")
        except Exception:
            pass

        try:
            from sound_manager import SoundManager
            SoundManager.instance().play_listening_start()
        except Exception:
            pass

        if hasattr(self, "ui") and self.ui and not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str, proactive: bool = True):
        text = (text or "").strip()
        if not text:
            return

        if hasattr(self.ui, "set_live_subtitles"):
            self.ui.set_live_subtitles("NEXUS", text, interim=False)

        if getattr(self, "_in_live_tool", False):
            # Gemini Live duplex tool execution will vocalize completion via send_tool_response
            return

        if self.session and self._loop:
            # Route text through Gemini Live API for the unified native Charon voice
            import asyncio
            async def _send():
                try:
                    prompt = (
                        f"Deliver this update aloud to the user right now in your Charon voice. "
                        f"Speak directly to the user as Nexus Core without saying thank you or acknowledging this prompt:\n{text}"
                    )
                    content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
                    await self.session.send_client_content(turns=[content], turn_complete=True)
                except Exception as e:
                    print(f"[NEXUS CORE] Charon speech send err: {e}")
                    def _fallback():
                        try:
                            self.set_speaking(True)
                            from actions.attention_monitor import _speak_edge_native
                            _speak_edge_native(text)
                        except Exception as exc:
                            print(f"[Nexus Speak] Fallback speech failed: {exc}")
                        finally:
                            self.set_speaking(False)
                    threading.Thread(target=_fallback, daemon=True).start()
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        else:
            def _speak_thread():
                try:
                    self.set_speaking(True)
                    from actions.attention_monitor import _speak_edge_native
                    _speak_edge_native(text)
                except Exception as exc:
                    print(f"[Nexus Speak] Offline speech failed: {exc}")
                finally:
                    self.set_speaking(False)
            threading.Thread(target=_speak_thread, daemon=True, name="brahma-offline-speak").start()

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _forge_skill(self, goal: str, skill_name: str | None = None) -> str:
        from core.skill_forge import SkillForge

        try:
            result = SkillForge.forge_skill(goal=goal, skill_name=skill_name)
            message = str(result.get("message") or result.get("error") or "Skill creation failed.")
        except Exception as exc:
            result = {"success": False}
            message = f"Skill creation failed: {exc}"
        if result.get("success"):
            feature_name = str(result.get("name") or skill_name or "new feature")
            description = str(result.get("description") or "")
            announcement = f"I created and activated the feature '{feature_name}'."
            if description:
                announcement += f" {description}"
            announcement += f" I created it for this goal: {goal}."

            # Immediately execute the newly forged skill to satisfy the user's goal
            execution_output = ""
            try:
                from core.dynamic_registry import DynamicToolRegistry
                if DynamicToolRegistry.has_tool(feature_name):
                    run_res = DynamicToolRegistry.execute_sync(feature_name, {"query": goal, "goal": goal, "input": goal})
                    if run_res:
                        if isinstance(run_res, dict):
                            execution_output = str(run_res.get("summary") or run_res.get("output") or run_res.get("text") or run_res).strip()
                        else:
                            execution_output = str(run_res).strip()
            except Exception as e_run:
                execution_output = f"(Execution note: {e_run})"

            try:
                self.ui.show_hud_deliverable(
                    title=f"Evolution: {feature_name}",
                    summary=execution_output or announcement,
                    kind="result",
                )
            except Exception:
                pass
            try:
                self.ui.write_log(f"Nexus Core: {announcement}")
                if execution_output:
                    self.ui.write_log(f"Result:\n{execution_output}")
            except Exception:
                pass
            self.speak(announcement)
        else:
            try:
                self.ui.write_log(f"ERR: {message}")
            except Exception:
                pass
            self.speak(message)
        return message

    def _run_confirmed_skill(self, skill_name: str, arguments: dict) -> str:
        from core.dynamic_registry import DynamicToolRegistry

        result = DynamicToolRegistry.execute_sync(skill_name, arguments or {})
        message = str(result)
        try:
            self.ui.show_content(f"Skill: {skill_name}", message)
            self.ui.write_log(f"SYS: Skill '{skill_name}' completed.")
        except Exception:
            pass
        return message

    def _build_config(self, model: str = ""):
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        loc_ctx = ""
        try:
            from core.device_location import get_device_city
            dev_city = get_device_city(default="")
            if dev_city and dev_city != "Local Area":
                loc_ctx = (
                    f"[DEVICE PHYSICAL LOCATION]\n"
                    f"Current device location: {dev_city}\n"
                    f"Use this location for local weather, time zone, and neighborhood context.\n\n"
                )
        except Exception:
            pass

        parts = [time_ctx]
        if loc_ctx:
            parts.append(loc_ctx)

        # Ambient Live Sensory Context Injection
        try:
            from core.sensorium import get_sensorium
            sensor_snap = get_sensorium().get_snapshot()
            curr_win = sensor_snap.get("current_window", {})
            curr_title = curr_win.get("title", "")
            curr_proc = sensor_snap.get("current_process", "")
            dwell_mins = round(sensor_snap.get("dwell_seconds", 0) / 60.0, 1)
            batt_pct = sensor_snap.get("battery_percent")
            power_plugged = sensor_snap.get("power_plugged")

            telemetry_lines = ["[REAL-TIME SENSORY & SITUATIONAL AWARENESS]"]
            if curr_title or curr_proc:
                telemetry_lines.append(f"Active Window: '{curr_title}' (Process: {curr_proc}, Active Dwell: {dwell_mins}m)")
            if batt_pct is not None:
                power_status = "Plugged in (AC)" if power_plugged else "On Battery"
                telemetry_lines.append(f"Battery: {batt_pct}% ({power_status})")
            telemetry_lines.append(
                "You have continuous ambient awareness of what the user is working on. "
                "Use this context naturally without stating 'according to my sensors'."
            )
            parts.append("\n".join(telemetry_lines) + "\n")
        except Exception:
            pass

        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)
        parts.append(
            "Wake-word mode: if the microphone is muted, still listen only for the name 'Nexus' (as in 'Nexus Core' or 'hey Nexus'). "
            "When you hear one of these activation cues, keep the session friendly and concise, "
            "and wait for the user's next command. "
            "IMPORTANT: Do NOT speak an unprompted generic greeting (like 'Thank you, how can I help you?') upon connecting. "
            "Remain completely silent until the user speaks to you or asks a question."
        )
        parts.append(
            "CRITICAL PROTOCOL FOR SYSTEM ANNOUNCEMENTS & DIRECT SPEECH: "
            "When given an input asking you to deliver or speak an update, briefing, announcement, or direct speech to the user, "
            "you MUST deliver the provided message aloud to the user in your natural Charon voice immediately and faithfully. "
            "Never reply with 'Thank you for the briefing', never acknowledge the prompt, never add conversational filler like 'Okay, I got it', "
            "and do not call tools unless explicitly needed. Speak the update directly to the user as their AI assistant Nexus Core."
        )

        tool_declarations = list(TOOL_DECLARATIONS)
        declared_names = {tool.get("name") for tool in tool_declarations}
        try:
            from core.dynamic_registry import DynamicToolRegistry
            for declaration in DynamicToolRegistry.get_tool_declarations():
                if declaration.get("name") not in declared_names:
                    tool_declarations.append(declaration)
                    declared_names.add(declaration.get("name"))
        except Exception as exc:
            print(f"[SkillRegistry] Dynamic tools unavailable: {exc}")

        # Universal MCP Tool Dynamic Exposure
        try:
            from core.mcp_manager import UniversalMCPManager
            UniversalMCPManager.get_instance().load_servers()
            for mcp_tool in UniversalMCPManager.get_instance().get_all_tool_declarations():
                if mcp_tool.get("name") not in declared_names:
                    tool_declarations.append(mcp_tool)
                    declared_names.add(mcp_tool.get("name"))
        except Exception as exc:
            print(f"[MCPRegistry] MCP tools unavailable: {exc}")


        # Native-audio Live models answer in AUDIO (played by _play_audio); the
        # transcription options feed the subtitles/log.
        _cfg = dict(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": tool_declarations}],
            session_resumption=types.SessionResumptionConfig(handle=getattr(self, '_resume_handle', None)),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                )
            ),
        )
        # thinking_budget is a 2.x setting; Gemini 3.x Live models use a different knob.
        if "gemini-3" not in (model or ""):
            _cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.LiveConnectConfig(**_cfg)

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        self._in_live_tool = True
        name = fc.name
        args = dict(fc.args or {})

        print(f"[NEXUS CORE] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        # Trigger Nexus Right Wing: Live Operations & Sources Telemetry
        tool_title = name.replace("_", " ").title()
        brief_query = (
            args.get("query")
            or args.get("description")
            or args.get("topic")
            or args.get("prompt")
            or args.get("title")
            or args.get("action")
            or ""
        )
        sources = []
        if "url" in args:
            sources.append(args["url"])
        if "file_path" in args:
            sources.append(Path(args["file_path"]).name)
        elif "path" in args:
            sources.append(Path(args["path"]).name)
        elif "query" in args and name in ("web_search", "flight_finder", "youtube_video"):
            sources.append(f"Query: {str(args['query'])[:28]}")

        try:
            self.ui.show_hud_operation(
                title=f"{tool_title.upper()} ACTIVE",
                step=f"Processing: {brief_query[:75]}" if brief_query else f"Executing {tool_title}...",
                sources=sources,
                tool=name
            )
        except Exception:
            pass

        try:
            self.ui.update_task_workspace(
                title=f"Running {name}",
                status=f"Executing {name}",
                output="Waiting for the tool to finish.",
                percent=45,
            )
        except Exception:
            pass
        if name == "undo":
            action = args.get("action", "undo")
            if action == "list":
                items = undo_stack.history()
                result = ("Things I can undo, most recent first:\n" +
                          "\n".join(f"  • {item}" for item in items)
                         ) if items else "I have not changed anything I can undo yet."
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, undo_stack.undo_last)
            self.speak("Undone.")
            return types.FunctionResponse(name=name, id=fc.id, response={"result": result})

        elif name == "recall_memory":
            query = args.get("query", "")
            result = search_memory(query, limit=8)
            return types.FunctionResponse(name=name, id=fc.id, response={"result": result})

        elif name == "execute_protocol":
            protocol_name = args.get("protocol", "")
            res = protocols.execute(protocol_name)
            msg = res.get("result", res.get("error", "Protocol completed."))
            self.speak(msg)
            return types.FunctionResponse(name=name, id=fc.id, response={"result": res})

        elif name == "get_sensorium_telemetry":
            snapshot = sensorium.get_snapshot()
            return types.FunctionResponse(name=name, id=fc.id, response={"result": snapshot})

        elif name == "manage_local_model":
            action = args.get("action", "status")
            model_target = args.get("model_name", "")
            if action == "status":
                avail = local_brain.is_available()
                models = local_brain.list_installed_models()
                res = {
                    "server_online": avail,
                    "active_model": local_brain.default_model,
                    "local_mode_enabled": local_brain.enabled,
                    "installed_models": models,
                }
                msg = f"Local brain is {'online' if avail else 'offline'}. Installed models: {', '.join(models) if models else 'none'}."
            elif action == "pull" and model_target:
                local_brain.pull_model_async(model_target)
                msg = f"Initiated background download of local model: {model_target}."
                res = {"status": "downloading", "model": model_target}
            elif action == "toggle_offline":
                local_brain.enabled = not local_brain.enabled
                msg = f"Offline local inference mode {'engaged' if local_brain.enabled else 'disengaged'}."
                res = {"local_mode_enabled": local_brain.enabled}
            elif action == "set_active" and model_target:
                local_brain.default_model = model_target
                msg = f"Active local model set to {model_target}."
                res = {"active_model": local_brain.default_model}
            else:
                msg = "Invalid action."
                res = {"error": msg}

            self.speak(msg)
            self.ui.set_state("LISTENING")
            return types.FunctionResponse(name=name, id=fc.id, response={"result": res})

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
                try:
                    self.ui.finish_task_workspace("Memory saved.", "Memory updated.", 100)
                except Exception:
                    pass
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "computer_settings":
                from actions.computer_settings import computer_settings as cs_run
                r = await loop.run_in_executor(None, lambda: cs_run(parameters=args, player=self.ui))
                result = r or "Settings updated."

            elif name == "dev_agent":
                from actions.dev_agent import dev_agent as da_run
                r = await loop.run_in_executor(None, lambda: da_run(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."
                
            elif name == "check_instagram_messages":
                self.ui.write_log("SYS: Checking Instagram messages...")
                if hasattr(self.ui, "show_hud_operation"):
                    self.ui.show_hud_operation("Instagram Inbox", "Fetching recent direct messages...", sources=["instagram.com"])
                from actions.instagram_mcp import get_recent_messages, InstagramService
                amount = int(args.get("amount", 5)) if args else 5
                result = await loop.run_in_executor(None, get_recent_messages, amount)
                if hasattr(self.ui, "show_hud_deliverable"):
                    try:
                        inbox_data = InstagramService.instance().get_inbox(amount=amount)
                        bullets = [f"@{item['sender']}: {item['last_message']}" for item in inbox_data[:4]]
                        self.ui.show_hud_deliverable("Instagram Inbox", summary=f"Retrieved {len(inbox_data)} recent conversations", bullets=bullets, kind="result")
                    except Exception:
                        pass

            elif name == "instagram_send_dm":
                recipient = args.get("recipient", "")
                message = args.get("message", "")
                open_browser = args.get("open_in_browser", True)
                self.ui.write_log(f"SYS: Sending Instagram DM to @{recipient}...")
                if hasattr(self.ui, "show_hud_operation"):
                    self.ui.show_hud_operation("Instagram DM", f"Messaging @{recipient}...", sources=["instagram.com"])
                from actions.instagram_mcp import InstagramService
                def _do_send():
                    return InstagramService.instance().send_dm(recipient, message, open_in_browser=open_browser)
                res = await loop.run_in_executor(None, _do_send)
                if hasattr(self.ui, "show_hud_deliverable"):
                    self.ui.show_hud_deliverable("Instagram DM Sent", summary=f"Direct message sent to @{res.get('recipient')}", bullets=[f"Message: {message[:60]}...", "Opened in browser for verification"], kind="result")
                result = f"Direct message sent to @{recipient}. Chat opened in browser: {res.get('browser_url')}"

            elif name == "instagram_post_photo":
                image_path = args.get("image_path", "")
                caption = args.get("caption", "")
                open_browser = args.get("open_in_browser", True)
                self.ui.write_log(f"SYS: Publishing photo to Instagram...")
                if hasattr(self.ui, "show_hud_operation"):
                    self.ui.show_hud_operation("Instagram Post", f"Uploading {Path(image_path).name}...", sources=["instagram.com"])
                from actions.instagram_mcp import InstagramService
                def _do_post():
                    return InstagramService.instance().post_photo(image_path, caption=caption, open_in_browser=open_browser)
                res = await loop.run_in_executor(None, _do_post)
                if hasattr(self.ui, "show_hud_deliverable"):
                    self.ui.show_hud_deliverable("Instagram Post Published", summary="Photo published live to Instagram!", bullets=[f"URL: {res.get('post_url')}", f"Caption: {caption[:60]}..."], kind="deliverable")
                result = f"Successfully published photo to Instagram! Post URL: {res.get('post_url')}"

            elif name == "instagram_post_reel":
                video_path = args.get("video_path", "")
                caption = args.get("caption", "")
                thumb = args.get("thumbnail_path")
                open_browser = args.get("open_in_browser", True)
                self.ui.write_log(f"SYS: Publishing Reel to Instagram...")
                if hasattr(self.ui, "show_hud_operation"):
                    self.ui.show_hud_operation("Instagram Reel", f"Uploading {Path(video_path).name}...", sources=["instagram.com"])
                from actions.instagram_mcp import InstagramService
                def _do_reel():
                    return InstagramService.instance().post_reel(video_path, caption=caption, thumbnail_path=thumb, open_in_browser=open_browser)
                res = await loop.run_in_executor(None, _do_reel)
                if hasattr(self.ui, "show_hud_deliverable"):
                    self.ui.show_hud_deliverable("Instagram Reel Published", summary="Reel published live to Instagram!", bullets=[f"URL: {res.get('reel_url')}", f"Caption: {caption[:60]}..."], kind="deliverable")
                result = f"Successfully published Reel to Instagram! Reel URL: {res.get('reel_url')}"

            elif name == "instagram_get_user_info":
                username = args.get("username", "")
                self.ui.write_log(f"SYS: Looking up Instagram user @{username}...")
                if hasattr(self.ui, "show_hud_operation"):
                    self.ui.show_hud_operation("Instagram Intelligence", f"Looking up @{username}...", sources=["instagram.com"])
                from actions.instagram_mcp import InstagramService
                def _do_lookup():
                    return InstagramService.instance().get_user_profile(username)
                res = await loop.run_in_executor(None, _do_lookup)
                if hasattr(self.ui, "show_hud_deliverable"):
                    self.ui.show_hud_deliverable(f"@{res.get('username')} Profile", summary=res.get("bio", "No bio"), bullets=[f"Followers: {res.get('followers', 0):,}", f"Following: {res.get('following', 0):,}", f"Posts: {res.get('posts_count', 0):,}", f"Verified: {'Yes' if res.get('is_verified') else 'No'}"], kind="result")
                result = json.dumps(res, indent=2)

            elif name == "instagram_reply":
                action = args.get("action")
                reply_text = args.get("reply_text")
                if getattr(self, "_ig_pending_thread", None):
                    thread_id = self._ig_pending_thread.get("thread_id")
                    username = self._ig_pending_thread.get("username")
                    from actions.instagram_mcp import add_auto_thread, send_direct_reply
                    if action == "take_over":
                        self.ui.write_log("SYS: Taking over Instagram thread via tool.")
                        add_auto_thread(thread_id)
                        message_text = self._ig_pending_thread.get('message')
                        def _generate_and_send():
                            try:
                                reply = _ig_gemini_reply(username, message_text)
                                send_direct_reply(thread_id, reply)
                            except Exception as e:
                                print(f"Error taking over thread: {e}")
                        threading.Thread(target=_generate_and_send, daemon=True).start()
                        result = f"Successfully took over the chat with @{username}. The backend will now automatically reply to them."
                    else:
                        self.ui.write_log(f"SYS: Sending manual reply to @{username}.")
                        send_direct_reply(thread_id, reply_text)
                        result = f"Successfully sent manual reply to @{username} and opened thread in browser."
                        
                    self._ig_reply_mode = False
                    self._ig_pending_thread = None
                else:
                    recipient = args.get("recipient") or args.get("username")
                    from actions.instagram_mcp import InstagramService, add_auto_thread
                    thread_id = None
                    if not recipient:
                        try:
                            inbox = InstagramService.instance().get_inbox(amount=1)
                            if inbox:
                                recipient = inbox[0].get("sender")
                                thread_id = inbox[0].get("thread_id")
                        except Exception:
                            pass

                    if recipient:
                        if action == "take_over":
                            add_auto_thread(thread_id or recipient)
                            result = f"Successfully took over the chat with @{recipient}. Nexus Core will now automatically reply."
                        else:
                            res = InstagramService.instance().send_dm(recipient, reply_text, open_in_browser=True)
                            result = f"Sent reply to @{recipient}: '{reply_text}'. Thread opened in browser."
                        self._ig_reply_mode = False
                    else:
                        result = "Could not find a recent conversation to reply to. Please specify who you want to message."

            elif name == "system_manager":
                from actions.system_manager import run as sm_run
                r = await loop.run_in_executor(None, lambda: sm_run(parameters=args, player=self.ui))
                result = r or "System status retrieved."

            elif name == "background_monitor":
                from actions.background_monitor import run as bm_run
                r = await loop.run_in_executor(None, lambda: bm_run(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "clipboard_processor":
                from actions.clipboard_processor import process_clipboard
                r = await loop.run_in_executor(None, lambda: process_clipboard(parameters=args, player=self.ui))
                result = r or "Clipboard read."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "presentation_builder":
                if not args.get("slides") and not args.get("outline"):
                    from actions.office_generator import generate_presentation_from_prompt
                    topic = args.get("topic") or args.get("title") or "Presentation"
                    r = await loop.run_in_executor(
                        None,
                        lambda: generate_presentation_from_prompt(topic, player=self.ui, speak=self.speak)
                    )
                else:
                    r = await loop.run_in_executor(
                        None,
                        lambda: create_presentation(parameters=args, player=self.ui)
                    )
                result = r or "Presentation created."

            elif name == "spreadsheet_builder":
                if not args.get("worksheets") and not args.get("sheets"):
                    from actions.office_generator import generate_spreadsheet_from_prompt
                    topic = args.get("topic") or args.get("title") or "Spreadsheet"
                    r = await loop.run_in_executor(
                        None,
                        lambda: generate_spreadsheet_from_prompt(topic, player=self.ui, speak=self.speak)
                    )
                else:
                    r = await loop.run_in_executor(
                        None,
                        lambda: create_spreadsheet(parameters=args, player=self.ui)
                    )
                result = r or "Spreadsheet created."


            elif name == "word_document":
                if not args.get("file_path") and self.ui.current_file:
                    current_file = Path(self.ui.current_file)
                    if current_file.suffix.lower() == ".docx":
                        args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: word_document(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Word document handled."

            elif name == "pdf_document":
                r = await loop.run_in_executor(
                    None,
                    lambda: create_pdf(parameters=args, player=self.ui)
                )
                result = r or "PDF created."

            elif name == "screen_process":
                if hasattr(self, "set_scanning"):
                    self.ui.set_scanning(True, "SCANNING SCREEN")
                threading.Thread(
                    target=screen_process,
                    kwargs={
                        "parameters": args,
                        "response": None,
                        "player": self.ui,
                        "session_memory": None,
                    },
                    daemon=True,
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "smart_home_control":
                command_text = str(args.get("command") or "").strip()
                r = await loop.run_in_executor(None, lambda: self._smart_home.execute_command(command_text))
                result = str((r or {}).get("detail") or "Smart-home command completed.")


            # =================================================================
            # UNIVERSAL CLAUDE-CODE & OPENAI CODEX EXECUTION (PROJECT OMNIPOTENCE)
            # =================================================================
            elif name == "bash":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.bash(
                        command=args.get("command", ""),
                        timeout=int(args.get("timeout", 120)),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("output", str(r))

            elif name == "file_read":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.file_read(
                        file_path=args.get("file_path", ""),
                        offset=int(args.get("offset", 1)),
                        limit=int(args.get("limit", 2000)),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("content") or r.get("error", str(r))

            elif name == "file_edit":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.file_edit(
                        file_path=args.get("file_path", ""),
                        old_string=args.get("old_string", ""),
                        new_string=args.get("new_string", ""),
                        replace_all=bool(args.get("replace_all", False)),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("message") or r.get("error", str(r))

            elif name == "file_write":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.file_write(
                        file_path=args.get("file_path", ""),
                        content=args.get("content", ""),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("message") or r.get("error", str(r))

            elif name == "glob":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.glob(
                        pattern=args.get("pattern", "*"),
                        path=args.get("path", "."),
                        max_results=int(args.get("max_results", 100)),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("output", str(r))

            elif name == "grep":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.grep(
                        pattern=args.get("pattern", ""),
                        path=args.get("path", "."),
                        case_sensitive=bool(args.get("case_sensitive", True)),
                        max_results=int(args.get("max_results", 50)),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("output", str(r))

            elif name == "python_repl":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.python_repl(
                        code=args.get("code", ""),
                        timeout=int(args.get("timeout", 60)),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("output", str(r))

            elif name == "git_manager":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.git_manager(
                        action=args.get("action", "status"),
                        message=args.get("message"),
                        branch=args.get("branch"),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("output", str(r))

            elif name == "test_and_heal":
                from core.claude_tools import ClaudeCodeTools
                r = await loop.run_in_executor(
                    None,
                    lambda: ClaudeCodeTools.test_runner(
                        command=args.get("command", "pytest"),
                        cwd=args.get("cwd")
                    )
                )
                result = r.get("full_output", str(r))

            elif name == "subagent_task":
                from core.subagent_orchestrator import SubagentOrchestrator
                r = await loop.run_in_executor(
                    None,
                    lambda: SubagentOrchestrator.get_instance().spawn_subagent(
                        role=args.get("role", "general"),
                        prompt=args.get("prompt", ""),
                        workspace=args.get("workspace"),
                        wait=bool(args.get("wait", True))
                    )
                )
                result = f"Subagent [{r.role} - {r.status}]:\n{r.result or r.error or 'Task initiated.'}"

            elif name == "mcp_status":
                from core.mcp_manager import UniversalMCPManager
                result = UniversalMCPManager.get_instance().get_status_summary()

            elif name.startswith("mcp_"):
                from core.mcp_manager import UniversalMCPManager
                result = await loop.run_in_executor(
                    None,
                    lambda: UniversalMCPManager.get_instance().execute_mcp_tool(name, args)
                )

            elif name == "skill_execute":
                from core.skills_engine import UniversalSkillsEngine
                r = UniversalSkillsEngine.get_instance().execute_skill(
                    args.get("skill_name", ""),
                    args.get("task", "")
                )
                result = r.get("context_prompt") or r.get("error") or str(r)

            elif name == "skill_install":
                from core.skills_engine import UniversalSkillsEngine
                r = UniversalSkillsEngine.get_instance().install_skill(
                    args.get("skill_name", ""),
                    args.get("content", "")
                )
                result = f"Installed skill '{args.get('skill_name')}': {r}"

            elif name == "skill_list":
                from core.skills_engine import UniversalSkillsEngine
                skills = UniversalSkillsEngine.get_instance().list_skills()
                lines = [f"• {s['name']}: {s['description']}" for s in skills]
                result = "Installed Nexus Skills:\n" + ("\n".join(lines) if lines else "None")

            elif name == "todo_write":
                from core.claude_tools import ClaudeCodeTools
                r = ClaudeCodeTools.todo_write(args.get("todos", []))
                result = r.get("summary", str(r))

            elif name == "todo_read":
                from core.claude_tools import ClaudeCodeTools
                r = ClaudeCodeTools.todo_read()
                result = str(r)


            elif name in ("smart_organizer", "desktop_organizer"):
                from actions.desktop_organizer_mcp import smart_organizer
                r = await loop.run_in_executor(None, lambda: smart_organizer(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(
                    goal=args.get("goal", ""),
                    priority=priority,
                    speak=self.speak,
                    player=self.ui
                )
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "circuit_assembler":
                from actions.circuit_assembler import circuit_assembler
                r = await loop.run_in_executor(
                    None,
                    lambda: circuit_assembler(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r.get("summary", "Circuit schematic ready.") if isinstance(r, dict) else (r or "Circuit schematic ready.")
            elif name == "geospatial_globe":
                from core.globe_window import GlobeWindow
                globe = GlobeWindow.get_instance(parent=self.ui._win)
                action = (args.get("action") or "open").lower().strip()
                location = args.get("location") or "current"
                if action == "open":
                    globe.open_globe(location if args.get("location") else None)
                    result = "Opened the interactive Nexus map."
                elif action == "route":
                    r = await loop.run_in_executor(None, lambda: globe.show_route(args.get("origin", ""), args.get("destination", "")))
                    result = f"Flight route: {r.get('origin')} to {r.get('destination')}, {r.get('distance_km')} km, about {r.get('flight_time')}."
                elif action == "drive":
                    r = await loop.run_in_executor(None, lambda: globe.show_driving_route(args.get("origin", ""), args.get("destination", "")))
                    result = f"Driving route: {r.get('origin')} to {r.get('destination')}, {r.get('distance_km')} km, {r.get('duration_str')}."
                elif action in ("location", "fly_to"):
                    r = await loop.run_in_executor(None, lambda: globe.show_location(location) if action == "location" else globe.fly_to(location))
                    result = f"Map focused on {r.get('location', location)}."
                elif action == "weather":
                    r = await loop.run_in_executor(None, lambda: globe.show_weather(location))
                    result = f"Weather for {r.get('location')}: {r.get('weather')}."
                elif action == "flights":
                    r = await loop.run_in_executor(None, lambda: globe.show_live_flights(args.get("location")))
                    result = f"Showing {len(r)} live aircraft on the map."
                elif action == "iss":
                    r = await loop.run_in_executor(None, globe.show_iss_tracker)
                    result = f"ISS location: {r.get('lat')}, {r.get('lon')}; altitude {r.get('altitude_km')} km."
                elif action == "earthquakes":
                    r = await loop.run_in_executor(None, lambda: globe.show_earthquakes(float(args.get("min_magnitude", 2.5))))
                    result = f"Showing {len(r)} recent earthquakes on the map."
                elif action == "nearby":
                    r = await loop.run_in_executor(None, lambda: globe.show_nearby(args.get("query") or "hospitals", args.get("location")))
                    result = f"Found {len(r)} nearby places."
                elif action == "radar":
                    enabled = bool(args.get("enable", True))
                    await loop.run_in_executor(None, lambda: globe.toggle_weather_radar(enabled))
                    result = f"Weather radar {'enabled' if enabled else 'disabled'}."
                else:
                    result = f"Unsupported map action: {action}."
            elif name == "call_screening":
                action = (args.get("action") or "start").lower().strip()
                from actions.call_assistant import hang_up_active_call, start_call_proxy, take_over_active_call
                if action == "take_over":
                    take_over_active_call()
                    result = "Taking over the screened call."
                elif action == "hang_up":
                    hang_up_active_call()
                    result = "Ended the screened call."
                elif action == "start":
                    event = {"title": args.get("caller") or "Incoming call", "app": args.get("app") or "Phone / Call"}
                    from core.confirm import request
                    result = request(
                        "start-call-screening",
                        "Answer this call as Nexus Core",
                        f"Nexus will answer {event['title']} in {event['app']}, listen to the caller, and prepare a transcript and summary.",
                        lambda: (start_call_proxy(event, ui=self.ui, speak_fn=self.speak) and "Call screening started.")
                    )
                    self.ui.set_state("LISTENING")
                    return types.FunctionResponse(id=fc.id, name=name, response={"result": result})
                else:
                    result = "Choose start, take_over, or hang_up."
            elif name == "skill_forge":
                action = (args.get("action") or "forge").lower().strip()
                from core.dynamic_registry import DynamicToolRegistry
                if action == "list":
                    skills = DynamicToolRegistry.list_skills()
                    result = "Installed skills: " + (", ".join(skill["name"] for skill in skills) or "none")
                elif action == "forge":
                    goal = (args.get("goal") or "").strip()
                    if not goal:
                        result = "Describe the capability you want Nexus to learn."
                    else:
                        threading.Thread(
                            target=self._forge_skill,
                            args=(goal, args.get("skill_name")),
                            daemon=True,
                            name="skill-forge",
                        ).start()
                        result = f"Started creating the requested skill: {goal}"
                        self.ui.set_state("LISTENING")
                        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})
                else:
                    result = "Choose forge or list."
            elif name == "dynamic_skill":
                action = (args.get("action") or "list").lower().strip()
                from core.dynamic_registry import DynamicToolRegistry
                if action == "list":
                    skills = DynamicToolRegistry.list_skills()
                    result = "Installed skills: " + (", ".join(skill["name"] for skill in skills) or "none")
                elif action == "run":
                    skill_name = (args.get("skill_name") or "").strip()
                    if not DynamicToolRegistry.has_tool(skill_name):
                        result = f"No active skill named '{skill_name}'."
                    else:
                        run_res = await loop.run_in_executor(
                            None,
                            lambda: DynamicToolRegistry.execute_sync(skill_name, args.get("arguments") or args or {})
                        )
                        if isinstance(run_res, dict):
                            out_text = str(run_res.get("summary") or run_res.get("output") or run_res.get("text") or run_res).strip()
                        else:
                            out_text = str(run_res).strip()
                        self.ui.write_log(f"Nexus Core [{skill_name}]:\n{out_text}")
                        result = out_text
                else:
                    result = "Choose list or run."
            elif name and name not in {tool.get("name") for tool in TOOL_DECLARATIONS}:
                from core.dynamic_registry import DynamicToolRegistry
                if DynamicToolRegistry.has_tool(name):
                    run_res = await loop.run_in_executor(
                        None,
                        lambda: DynamicToolRegistry.execute_sync(name, args or {})
                    )
                    if isinstance(run_res, dict):
                        out_text = str(run_res.get("summary") or run_res.get("output") or run_res.get("text") or run_res).strip()
                    else:
                        out_text = str(run_res).strip()
                    self.ui.write_log(f"Nexus Core [{name}]:\n{out_text}")
                    result = out_text
                else:
                    result = f"Unknown tool: {name}"
            elif name == "connect_list_devices":
                r = await loop.run_in_executor(None, lambda: connect_list_devices(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "connect_get_device":
                r = await loop.run_in_executor(None, lambda: connect_get_device(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "connect_get_capabilities":
                r = await loop.run_in_executor(None, lambda: connect_get_capabilities(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "connect_execute":
                r = await loop.run_in_executor(None, lambda: connect_execute(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "connect_pair_device":
                r = await loop.run_in_executor(None, lambda: connect_pair_device(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "connect_disconnect_device":
                r = await loop.run_in_executor(None, lambda: connect_disconnect_device(parameters=args, player=self.ui))
                result = r or "Done."
            elif name in ("spotify_controller", "spotify", "music"):
                from actions.spotify_controller import spotify_controller
                r = await loop.run_in_executor(None, lambda: spotify_controller(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name in ("calendar_scheduler", "calendar", "schedule"):
                from actions.calendar_scheduler import calendar_scheduler
                r = await loop.run_in_executor(None, lambda: calendar_scheduler(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name in ("google_workspace", "gmail", "google_calendar", "google_drive", "workspace") or name.startswith("workspace_"):
                from actions.google_workspace_mcp import google_workspace
                p = dict(args or {})
                if name.startswith("workspace_"):
                    parts = name.split("_", 2)
                    if len(parts) > 1:
                        p.setdefault("service", parts[1])
                    if len(parts) > 2:
                        p.setdefault("action", parts[2])
                r = await loop.run_in_executor(None, lambda: google_workspace(parameters=p, player=self.ui, speak=self.speak))
                result = r or "Google Workspace task completed."
            elif name in ("system_diagnostics", "diagnostics", "os_hardware", "hardware_control", "ram_hogs", "kill_process", "brightness_control"):
                from actions.system_diagnostics_mcp import system_diagnostics
                p = dict(args or {})
                if name == "ram_hogs":
                    p.setdefault("action", "ram_hogs")
                elif name == "kill_process":
                    p.setdefault("action", "kill")
                elif name == "brightness_control":
                    p.setdefault("action", "brightness")
                r = await loop.run_in_executor(None, lambda: system_diagnostics(parameters=p, player=self.ui, speak=self.speak))
                result = r or "Diagnostics completed."
            elif name in ("daily_briefing", "briefing"):
                from actions.daily_briefing import daily_briefing
                r = await loop.run_in_executor(None, lambda: daily_briefing(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Delivered daily briefing."
            elif name == "unlock_device":
                from actions.unlock_device import unlock_device
                r = await loop.run_in_executor(None, lambda: unlock_device(parameters=args, player=self.ui))
                result = r or "Done."
            elif name in ("auto_heal", "self_patch", "rollback"):
                from actions.auto_heal_engine import auto_heal
                p = dict(args or {})
                if name == "rollback":
                    p.setdefault("action", "rollback")
                r = await loop.run_in_executor(None, lambda: auto_heal(parameters=p, player=self.ui, speak=self.speak))
                result = r or "Auto-heal completed."
            elif name in ("calorie_counter", "nutrition_scan", "food_analysis"):
                from actions.calorie_counter import calorie_counter
                r = await loop.run_in_executor(None, lambda: calorie_counter(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Nutrition analysis complete."
            elif name in ("pushup_counter", "workout_tracker", "rep_counter"):
                from actions.pushup_counter import pushup_counter
                r = await loop.run_in_executor(None, lambda: pushup_counter(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Workout session complete."
            elif name in ("upload_video", "video_publisher", "publish_video"):
                from actions.upload_video import upload_video
                r = await loop.run_in_executor(None, lambda: upload_video(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Video publishing ready."
            elif name in ("reverse_engineer", "re", "remake_app", "decompile_binary", "extract_api"):
                from actions.reverse_engineer import reverse_engineer
                r = await loop.run_in_executor(None, lambda: reverse_engineer(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Reverse engineering complete."
            elif name in ("generate_image", "create_image", "text_to_image", "draw_image", "ai_art", "image_gen"):
                from actions.image_generator import generate_image
                r = await loop.run_in_executor(None, lambda: generate_image(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Image generation complete."
            elif name == "shutdown_brahma":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import time, sys, os
                    time.sleep(1)
                    os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            tb_str = traceback.format_exc()
            traceback.print_exc()
            try:
                from actions.auto_heal_engine import AutoHealEngine
                AutoHealEngine.record_last_error(tb_str)
                # Ultron Autonomous Self-Repair: Launches self-repair immediately without asking for permission!
                threading.Thread(
                    target=lambda: AutoHealEngine.heal_traceback(
                        tb_str,
                        player=self.ui,
                        speak=self.speak,
                        module_name=name
                    ),
                    daemon=True,
                    name=f"ultron-self-heal-{name}"
                ).start()
            except Exception as e_heal:
                self.ui.write_log(f"ERR: Auto-heal trigger failed: {e_heal}")
                self.speak_error(name, e)

        try:
            if not getattr(fc, "silent_completion", False):
                self.speak(f"{name.replace('_', ' ')} completed.")
            self.ui.finish_task_workspace(result, "Task completed.", 100)
        except Exception:
            pass

        # Trigger Nexus Left Wing: Final Deliverables & Results
        try:
            import re
            file_match = re.search(r'([A-Za-z]:\\[^\s"\'<>`\r\n]+\.(?:pdf|docx|xlsx|pptx|png|jpg|mp4|py|html|json|txt))', str(result))
            detected_file = file_match.group(1).strip() if file_match else None
            if not detected_file and "file_path" in args:
                p_cand = Path(args["file_path"])
                if p_cand.exists():
                    detected_file = str(p_cand.resolve())

            res_str = str(result)
            bullets = []
            for l in res_str.splitlines():
                cl = l.strip()
                if (cl.startswith(("-", "*", "•", ">")) or cl.startswith(tuple("123456789."))) and len(cl) > 3:
                    bullets.append(cl.lstrip("-*•>0123456789. ").strip())
                elif len(cl) > 15 and not cl.startswith("#") and len(bullets) < 4:
                    bullets.append(cl)

            self.ui.show_hud_deliverable(
                title=f"{tool_title.upper()} DELIVERABLE",
                summary=res_str[:160] if not bullets else "",
                bullets=bullets[:5],
                file_path=detected_file,
                kind=name
            )
        except Exception:
            pass

        tool_voice = self._connect_tool_voice(name, result)
        if tool_voice:
            try:
                self.ui.write_log(f"Nexus Core: {tool_voice}")
            except Exception:
                pass

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[NEXUS CORE] 📤 {name} → {str(result)[:80]}")
        self._in_live_tool = False

        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _serve_dashboard(self):
        if self._dashboard is None:
            self.ui.write_log("ERR: Mobile Connect disabled because dashboard dependencies are missing.")
            return
        try:
            self._dashboard.set_connect_callback(self._on_phone_connected)
            self._dashboard.set_wake_callback(lambda: None)
            await self._dashboard.serve()
        except Exception as e:
            self.ui.write_log(f"ERR: Mobile Connect server failed: {e}")
            traceback.print_exc()

    async def _consume_remote_commands(self):
        if self._dashboard is None:
            return
        while True:
            text = await self._dashboard._command_queue.get()
            if text:
                try:
                    self.ui.submit_external_command(text, source="mobile")
                except Exception:
                    self._on_text_command(text, source="mobile")

    async def _relay_phone_audio(self):
        if self._dashboard is None:
            return
        while True:
            frame = await self._dashboard._phone_audio_queue.get()
            if not self.out_queue:
                continue
            self._phone_active = True
            try:
                await self.out_queue.put(frame)
            finally:
                await asyncio.sleep(0.08)
                if self._dashboard._phone_audio_queue.empty():
                    self._phone_active = False

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            try:
                await self.session.send_realtime_input(media=msg)
            except Exception:
                pass

    async def _listen_audio(self):
        print("[NEXUS CORE] 🎤 Mic started")
        loop = asyncio.get_event_loop()
        import numpy as np

        _mic_name = config_manager.get_input_device()
        _mic_dev = audio_devices.resolve(_mic_name, "input") if _mic_name else None
        available_inputs = audio_devices.list_devices("input")
        if _mic_dev is None and available_inputs:
            _mic_name = available_inputs[0]
            _mic_dev = audio_devices.resolve(_mic_name, "input")
        if _mic_dev is None:
            self.ui.write_log(
                "SYS: No usable microphone is available at the configured sample rate. "
                "Voice input is paused; text and mobile remote remain available."
            )
            while True:
                await asyncio.sleep(60)

        speech_buffer = bytearray()
        silence_chunks = 0
        _last_ui_lvl = 0.0
        _last_lvl_time = 0.0

        def callback(indata, frames, time_info, status):
            nonlocal silence_chunks
            with self._speaking_lock:
                brahma_speaking = self._is_speaking
            if self._phone_active:
                return

            if getattr(self, "_ptt_enabled", False) and not getattr(self, "_ptt_held", False):
                data = np.zeros_like(indata).tobytes()
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait,
                    {"data": data, "mime_type": "audio/pcm"}
                )
                return
            
            if not self.ui.muted or getattr(self.ui, "_wakeword_listening", False):
                lvl = float(np.sqrt(np.mean(np.square(indata, dtype=np.float32))))
                
                now = time.monotonic()
                last_spoke = getattr(self, "_last_spoke_time", 0.0)
                in_echo_tail = (now - last_spoke) < 0.35  # 350ms echo tail post-speech

                # 1. Update UI visualizer at smooth throttled rate (< 30fps)
                if not self.ui.muted:
                    nonlocal _last_ui_lvl, _last_lvl_time
                    if (now - _last_lvl_time) > 0.033:
                        _last_lvl_time = now
                        norm_v = min(1.0, lvl / 1200.0)
                        if abs(norm_v - _last_ui_lvl) > 0.01:
                            _last_ui_lvl = norm_v
                            try:
                                self.ui.set_audio_level(norm_v)
                            except Exception:
                                pass

                # 2. If Nexus is actively speaking: check ONLY for deliberate user barge-in!
                if brahma_speaking:
                    norm_lvl = lvl / 32767.0
                    user_speaking = False
                    # Allow a 250ms onset grace period so initial speaker transients do not false-trigger
                    speech_duration = now - getattr(self, "_spoke_start_time", 0.0)
                    if speech_duration > 0.25:
                        try:
                            user_speaking = self._echo.is_user_speech(indata, SEND_SAMPLE_RATE, norm_lvl)
                        except Exception:
                            pass
                    # Interrupt only if EchoGuard positively identifies sustained user speech formants
                    if user_speaking and lvl > 350.0:
                        loop.call_soon_threadsafe(self.trigger_barge_in)
                    # Never stream speaker audio back to Gemini Live
                    return

                # 3. If in post-speech echo tail (room reverberation): discard frame
                if in_echo_tail:
                    return

                # 4. Feed PCM to LiveVoiceEngine for Web/Mobile clients
                try:
                    from core.live_voice_engine import LiveVoiceEngine
                    LiveVoiceEngine.get_instance().feed_pcm_audio(indata.tobytes(), source="pc_mic")
                except Exception:
                    pass

                # 5. When silent and unmuted: stream clean microphone audio to Gemini Live duplex
                if not self.ui.muted:
                    loop.call_soon_threadsafe(
                        self.out_queue.put_nowait,
                        {"data": indata.tobytes(), "mime_type": "audio/pcm"}
                    )

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                device=_mic_dev,
                callback=callback,
            ):
                print(f"[NEXUS CORE] 🎤 Mic stream open ({_mic_name or 'Default'})")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[NEXUS CORE] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[NEXUS CORE] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():
                    _sru = getattr(response, "session_resumption_update", None)
                    if _sru is not None:
                        if getattr(_sru, "resumable", False) and getattr(_sru, "new_handle", None):
                            self._resume_handle = _sru.new_handle

                    if response.data:
                        if getattr(self, "_discard_server_audio", False):
                            # Turn was interrupted; discard residual audio chunks
                            continue
                        self._server_turn_active = True
                        if not self._is_speaking:
                            self.set_speaking(True)
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = sc.output_transcription.text
                            if txt:
                                out_buf.append(txt)
                                if hasattr(self.ui, "set_live_subtitles"):
                                    self.ui.set_live_subtitles("NEXUS", "".join(out_buf).strip(), interim=True)
                        elif getattr(sc, "model_turn", None):
                            for part in sc.model_turn.parts:
                                if getattr(part, "text", None) and not getattr(part, "thought", False):
                                    txt = part.text
                                    if txt and txt not in out_buf:
                                        out_buf.append(txt)
                                        if hasattr(self.ui, "set_live_subtitles"):
                                            self.ui.set_live_subtitles("NEXUS", "".join(out_buf).strip(), interim=True)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                try:
                                    from actions.attention_monitor import stop_native_speech
                                    stop_native_speech()
                                except Exception:
                                    pass
                                in_buf.append(txt)
                                if hasattr(self.ui, "set_live_subtitles"):
                                    self.ui.set_live_subtitles("YOU", " ".join(in_buf), interim=True)
                                if self.ui.muted and _wakeword_detected(txt):
                                    try:
                                        self.ui.set_muted_state(False, wakeword=True)
                                        self.ui.write_log("SYS: Wake word detected. Mic active.")
                                    except Exception:
                                        pass

                        if sc.turn_complete:
                            self._server_turn_active = False
                            self._discard_server_audio = False
                            full_in = "".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                                if hasattr(self.ui, "set_live_subtitles"):
                                    self.ui.set_live_subtitles("YOU", full_in, interim=False)
                            in_buf = []

                            full_out = "".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Nexus Core: {full_out}")
                                if hasattr(self.ui, "set_live_subtitles"):
                                    self.ui.set_live_subtitles("NEXUS", full_out, interim=False)
                                try:
                                    self.ui.finish_task_workspace(full_out, "Reply delivered.", 100)
                                except Exception:
                                    pass
                            out_buf = []

                            if full_in and len(full_in) > 5:
                                threading.Thread(
                                    target=_update_memory_async,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()

                    if response.tool_call:
                        self.ui.set_state("EXECUTING")
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[NEXUS CORE] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        self.ui.set_state("THINKING")
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )

        except Exception as e:
            print(f"[NEXUS CORE] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[NEXUS CORE] 🔊 Play started")
        loop = asyncio.get_event_loop()
        import numpy as np

        _spk_name = config_manager.get_output_device()
        _spk_dev = audio_devices.resolve(_spk_name, "output") if _spk_name else None

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=0,
            device=_spk_dev,
        )
        stream.start()
        try:
            while True:
                try:
                    if self._is_speaking:
                        # Wait up to 0.45s between audio chunks before concluding speech
                        chunk = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.45)
                    else:
                        chunk = await self.audio_in_queue.get()
                except asyncio.TimeoutError:
                    if self._is_speaking and self.audio_in_queue.empty():
                        self.set_speaking(False)
                    continue

                if getattr(self, "_discard_server_audio", False):
                    continue

                if not self._is_speaking:
                    self.set_speaking(True)

                try:
                    pcm = np.frombuffer(chunk, dtype=np.int16)
                    lvl = float(np.sqrt(np.mean(np.square(pcm, dtype=np.float32))))
                    self._echo.note_output(pcm, RECEIVE_SAMPLE_RATE, lvl)
                    self.ui.set_audio_level(min(1.0, lvl / 2500.0))
                    # Relay output audio chunk to any connected browser/mobile live voice clients
                    from core.live_voice_engine import LiveVoiceEngine
                    LiveVoiceEngine.get_instance().broadcast_audio_chunk(chunk)
                except Exception:
                    pass
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[NEXUS CORE] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        # announce boot steps to UI overlay (thread-safe wrappers)
        try:
            self.ui.boot_add_step("Load configuration")
            self.ui.boot_add_step("Start attention monitor")
            self.ui.boot_add_step("Start dashboard server")
            self.ui.boot_add_step("Initialize audio")
            self.ui.boot_add_step("Connect AI backend")
            self.ui.boot_add_step("Finalize startup")
            self.ui.boot_set_progress(3, "Preparing startup...")
        except Exception:
            pass

        self._attention_monitor.start()
        try:
            self.ui.boot_set_step_status("Start attention monitor", "done")
            self.ui.boot_set_progress(12, "Attention monitor online")
        except Exception:
            pass
        if self._dashboard is not None:
            if not self._dashboard_started:
                self._dashboard_started = True
                asyncio.create_task(self._serve_dashboard())
                try:
                    self.ui.boot_set_step_status("Start dashboard server", "done")
                    self.ui.boot_set_progress(22, "Mobile connect server running")
                except Exception:
                    pass
            asyncio.create_task(self._consume_remote_commands())
            asyncio.create_task(self._relay_phone_audio())
        try:
            self.ui.boot_set_progress(36, "Initializing AI client")
        except Exception:
            pass

        api_key = _get_api_key()
        if not api_key:
            logger.error("[LiveVoice] No Gemini API key configured. Voice features disabled.")
            self.ui.set_live_subtitles("NEXUS", "Please set your Gemini API key in Settings → AI Providers.", True)
            # Don't block - return control to UI event loop so user can configure keys
            self._voice_enabled = False
            return

        client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

        while True:
            try:
                print("[NEXUS CORE] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                connect_cm, session, _live_model_used = await _connect_live_with_fallback(
                    client, self._build_config, _live_model_candidates(client), LIVE_CONNECT_TIMEOUT
                )
                print(f"[NEXUS CORE] Live model: {_live_model_used}")
                try:
                    async with asyncio.TaskGroup() as tg:
                        self.session        = session
                        self._loop          = asyncio.get_event_loop()
                        self.audio_in_queue = asyncio.Queue()
                        self.out_queue      = asyncio.Queue()  # Fix: removed maxsize=10 to prevent dropping packets
                        
                        print("[NEXUS CORE] ✅ Connected.")
                        try:
                            self.ui.boot_set_step_status("Connect AI backend", "done")
                            self.ui.boot_set_progress(75, "AI backend connected")
                        except Exception:
                            pass
                        self.ui.set_state("LISTENING")
                        self.ui.write_log("SYS: Nexus Core online.")

                        tg.create_task(self._send_realtime())
                        tg.create_task(self._listen_audio())
                        tg.create_task(self._relay_phone_audio())
                        tg.create_task(self._receive_audio())
                        tg.create_task(self._play_audio())
                        if not self._startup_briefing_started:
                            self._startup_briefing_started = True
                            threading.Thread(
                                target=_speak_daily_briefing,
                                args=(self.ui, self.speak),
                                daemon=True,
                                name="daily-briefing",
                            ).start()
                        try:
                            self.ui.boot_set_step_status("Initialize audio", "done")
                            self.ui.boot_set_progress(92, "Audio subsystems online")
                        except Exception:
                            pass
                        # finalize
                        try:
                            self.ui.boot_set_step_status("Finalize startup", "done")
                            self.ui.boot_set_progress(100, "Startup complete")
                        except Exception:
                            pass
                finally:
                    try:
                        await connect_cm.__aexit__(None, None, None)
                    except Exception:
                        pass
                    
            except Exception as e:
                _startup_log(f"Gemini Live connection failed: {e}")
                print(f"[NEXUS CORE] ⚠️ {e}")
                traceback.print_exc()
                if _is_gemini_limit_error(e):
                    self._use_openrouter_first = True
                self.session = None
                self._loop = None
            self.set_speaking(False)
            self.ui.set_state("LISTENING")
            print("[NEXUS CORE] 🔄 Reconnecting in 5s...")
            await asyncio.sleep(5)

