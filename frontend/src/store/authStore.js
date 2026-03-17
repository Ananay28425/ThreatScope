import { create } from "zustand";
import { persist } from "zustand/middleware";
import api from "../services/api.js";

export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,

      login: async (email, password) => {
        const { data } = await api.post("/api/auth/login", { email, password });
        api.defaults.headers.common["Authorization"] = `Bearer ${data.access_token}`;
        set({ token: data.access_token });
        return data;
      },

      logout: () => {
        delete api.defaults.headers.common["Authorization"];
        set({ token: null, user: null });
      },

      initToken: () => {
        const { token } = get();
        if (token) {
          api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
        }
      },
    }),
    { name: "threatscope-auth", partialize: (s) => ({ token: s.token }) }
  )
);
