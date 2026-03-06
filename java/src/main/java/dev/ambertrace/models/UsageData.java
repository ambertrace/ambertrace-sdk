package dev.ambertrace.models;

import java.util.LinkedHashMap;
import java.util.Map;

/** Token usage statistics from the LLM response. */
public final class UsageData {

    private final int promptTokens;
    private final int completionTokens;
    private final int totalTokens;

    public UsageData(int promptTokens, int completionTokens, int totalTokens) {
        this.promptTokens = promptTokens;
        this.completionTokens = completionTokens;
        this.totalTokens = totalTokens;
    }

    public int getPromptTokens() { return promptTokens; }
    public int getCompletionTokens() { return completionTokens; }
    public int getTotalTokens() { return totalTokens; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("prompt_tokens", promptTokens);
        map.put("completion_tokens", completionTokens);
        map.put("total_tokens", totalTokens);
        return map;
    }
}
