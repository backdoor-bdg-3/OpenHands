import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

// This is a replacement for the model selector component that only displays the hardcoded model
// without any selection capability

interface ModelSelectorProps {
  isDisabled?: boolean;
  models?: Record<string, { separator: string; models: string[] }>;
  currentModel?: string;
}

export function ModelSelector({
  isDisabled,
  models,
  currentModel,
}: ModelSelectorProps) {
  const { t } = useTranslation();
  
  // Hardcoded model information - always showing this regardless of props
  const modelName = "meta-llama/CodeLlama-13b-Instruct-hf";
  const provider = "Hugging Face";

  return (
    <div className="w-full p-4 bg-tertiary border border-[#717888] rounded-md">
      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold">{t(I18nKey.LLM$PROVIDER_AND_MODEL || "Provider & Model")}</h3>
        <p className="text-md">
          <span className="font-medium">{provider}</span>: {modelName}
        </p>
        <p className="text-sm text-gray-400 mt-2">
          {t(I18nKey.MODEL_SELECTOR$FIXED_MODEL_MESSAGE || "This model is fixed and cannot be changed.")}
        </p>
      </div>
    </div>
  );
}
