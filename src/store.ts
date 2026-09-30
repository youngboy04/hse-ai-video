import { create } from "zustand";
import type { Page } from "./types";
interface UIStore {
  page: Page;
  setPage: (page: Page) => void;
  token: string;
  setToken: (token: string) => void;
  toast: string;
  notify: (message: string) => void;
}
let timer: ReturnType<typeof setTimeout>;
export const useUI = create<UIStore>((set) => ({
  page: "overview",
  setPage: (page) => set({ page }),
  token: sessionStorage.getItem("hse-token") || "",
  setToken: (token) => {
    sessionStorage.setItem("hse-token", token);
    set({ token });
  },
  toast: "",
  notify: (toast) => {
    clearTimeout(timer);
    set({ toast });
    timer = setTimeout(() => set({ toast: "" }), 4500);
  },
}));
