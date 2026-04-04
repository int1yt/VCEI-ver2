/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_REAL_IDS_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
