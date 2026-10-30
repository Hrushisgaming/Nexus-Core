package com.nexus.connect.pairing

import com.nexus.connect.core.PairingOffer
import org.json.JSONObject

object PairingPayloadParser {
    fun parse(raw: String): PairingOffer? {
        if (raw.isBlank()) return null
        return try {
            PairingOffer.fromJson(JSONObject(raw))
        } catch (_: Exception) {
            null
        }
    }
}
