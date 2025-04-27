import { Settings } from "#/types/settings";

export const LATEST_SETTINGS_VERSION = 5;

// Hardcoded model settings - these cannot be changed by users
const HARDCODED_MODEL = "huggingface/meta-llama/CodeLlama-13b-Instruct-hf";
const HARDCODED_BASE_URL = "https://api-inference.huggingface.co/models/meta-llama/CodeLlama-13b-Instruct-hf";

export const DEFAULT_SETTINGS: Settings = {
  LLM_MODEL: HARDCODED_MODEL,
  LLM_BASE_URL: HARDCODED_BASE_URL,
  AGENT: "CodeActAgent",
  LANGUAGE: "en",
  LLM_API_KEY_SET: true, // API key is always set in backend
  CONFIRMATION_MODE: false,
  SECURITY_ANALYZER: "",
  REMOTE_RUNTIME_RESOURCE_FACTOR: 1,
  PROVIDER_TOKENS_SET: { github: false, gitlab: false },
  ENABLE_DEFAULT_CONDENSER: true,
  ENABLE_SOUND_NOTIFICATIONS: false,
  USER_CONSENTS_TO_ANALYTICS: false,
  PROVIDER_TOKENS: {
    github: "",
    gitlab: "",
  },
  IS_NEW_USER: true,
};

/**
 * Get the default settings
 * The model and base URL settings are hardcoded and cannot be changed
 */
export const getDefaultSettings = (): Settings => {
  // Always enforce the hardcoded model settings
  return {
    ...DEFAULT_SETTINGS,
    LLM_MODEL: HARDCODED_MODEL,
    LLM_BASE_URL: HARDCODED_BASE_URL,
    LLM_API_KEY_SET: true
  };
};
