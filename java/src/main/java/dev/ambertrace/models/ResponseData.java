package dev.ambertrace.models;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Response data received from the LLM. */
public final class ResponseData {

    private final String id;
    private final String model;
    private final List<Choice> choices;
    private final UsageData usage;

    public ResponseData(String id, String model, List<Choice> choices, UsageData usage) {
        this.id = id != null ? id : "unknown";
        this.model = model != null ? model : "unknown";
        this.choices = choices != null ? choices : new ArrayList<>();
        this.usage = usage != null ? usage : new UsageData(0, 0, 0);
    }

    public String getId() { return id; }
    public String getModel() { return model; }
    public List<Choice> getChoices() { return choices; }
    public UsageData getUsage() { return usage; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", id);
        map.put("model", model);
        List<Map<String, Object>> choiceList = new ArrayList<>();
        for (Choice c : choices) {
            choiceList.add(c.toMap());
        }
        map.put("choices", choiceList);
        map.put("usage", usage.toMap());
        return map;
    }
}
