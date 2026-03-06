package dev.ambertrace.models;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Request data sent to the LLM. */
public final class RequestData {

    private final String model;
    private final List<Message> messages;
    private final Map<String, Object> parameters;

    public RequestData(String model, List<Message> messages, Map<String, Object> parameters) {
        this.model = model != null ? model : "unknown";
        this.messages = messages != null ? messages : new ArrayList<>();
        this.parameters = parameters != null ? parameters : new LinkedHashMap<>();
    }

    public String getModel() { return model; }
    public List<Message> getMessages() { return messages; }
    public Map<String, Object> getParameters() { return parameters; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("model", model);
        List<Map<String, Object>> msgList = new ArrayList<>();
        for (Message msg : messages) {
            msgList.add(msg.toMap());
        }
        map.put("messages", msgList);
        map.put("parameters", parameters);
        return map;
    }
}
