import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 10_000,
  headers: { "Content-Type": "application/json" },
});

// Response interceptor: log errors, handle 401 globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // Clear stored token and redirect to login
      localStorage.removeItem("threatscope-auth");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;
