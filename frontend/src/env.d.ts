/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the FastAPI + Socket.IO backend. */
  readonly VITE_BACKEND_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
