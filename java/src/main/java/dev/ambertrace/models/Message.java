package dev.ambertrace.models;

import java.util.LinkedHashMap;
import java.util.Map;

/** A chat message in the conversation. */
public final class Message {

    private final String role;
    private final String content;

    public Message(String role, String content) {
        this.role = role != null ? role : "unknown";
        this.content = content != null ? content : "";
    }

    public String getRole() { return role; }
    public String getContent() { return content; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("role", role);
        map.put("content", content);
        return map;
    }
}
