package dev.ambertrace.models;

import java.util.LinkedHashMap;
import java.util.Map;

/** A single choice in the LLM response. */
public final class Choice {

    private final int index;
    private final Message message;
    private final String finishReason;

    public Choice(int index, Message message, String finishReason) {
        this.index = index;
        this.message = message;
        this.finishReason = finishReason != null ? finishReason : "unknown";
    }

    public int getIndex() { return index; }
    public Message getMessage() { return message; }
    public String getFinishReason() { return finishReason; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("index", index);
        map.put("message", message.toMap());
        map.put("finish_reason", finishReason);
        return map;
    }
}
