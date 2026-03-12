package dev.ambertrace.models;

import java.util.LinkedHashMap;
import java.util.Map;

/** Token usage statistics from the LLM response. */
public final class UsageData {

    private final int promptTokens;
    private final int completionTokens;
    private final int totalTokens;
    private final Integer cachedTokens;
    private final Integer reasoningTokens;

    public UsageData(int promptTokens, int completionTokens, int totalTokens) {
        this(promptTokens, completionTokens, totalTokens, null, null);
    }

    public UsageData(int promptTokens, int completionTokens, int totalTokens,
                     Integer cachedTokens, Integer reasoningTokens) {
        this.promptTokens = promptTokens;
        this.completionTokens = completionTokens;
        this.totalTokens = totalTokens;
        this.cachedTokens = cachedTokens;
        this.reasoningTokens = reasoningTokens;
    }

    public int getPromptTokens() { return promptTokens; }
    public int getCompletionTokens() { return completionTokens; }
    public int getTotalTokens() { return totalTokens; }
    public Integer getCachedTokens() { return cachedTokens; }
    public Integer getReasoningTokens() { return reasoningTokens; }

    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("prompt_tokens", promptTokens);
        map.put("completion_tokens", completionTokens);
        map.put("total_tokens", totalTokens);
        map.put("cached_tokens", cachedTokens);
        map.put("reasoning_tokens", reasoningTokens);
        return map;
    }
}
