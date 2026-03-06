package dev.ambertrace.models;

import java.util.LinkedHashMap;
import java.util.Map;

/** Error information when an LLM call fails. */
public final class ErrorData {

    private final String type;
    private final String message;
    private final String code;

    public ErrorData(String type, String message, String code) {
        this.type = type != null ? type : "unknown";
        this.message = message != null ? message : "";
        this.code = code;
    }

    public String getType() { return type; }
    public String getMessage() { return message; }
    public String getCode() { return code; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("type", type);
        map.put("message", message);
        if (code != null) {
            map.put("code", code);
        }
        return map;
    }
}
