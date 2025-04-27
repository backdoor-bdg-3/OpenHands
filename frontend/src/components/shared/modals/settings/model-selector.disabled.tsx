/**
 * This file replaces the original model-selector.tsx to disable model selection in the UI.
 * The component now displays only the hardcoded model information without any selection capabilities.
 */
import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

export function ModelSelector() {
  const { t } = useTranslation();
  
  // Hardcoded model information
  const modelName = "meta-llama/CodeLlama-13b-Instruct-hf";
  const provider = "Hugging Face";

  return (
    <div className="w-full p-4 bg-tertiary border border-[#717888] rounded-md">
      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold">{t(I18nKey.LLM$PROVIDER_AND_MODEL)}</h3>
        <p className="text-md">
          {provider}: <span className="font-medium">{modelName}</span>
        </p>
        <p className="text-sm text-gray-400 mt-2">
          {t(I18nKey.MODEL_SELECTOR$FIXED_MODEL_MESSAGE)}
        </p>
      </div>
    </div>
  );
}
