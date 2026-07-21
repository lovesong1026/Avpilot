import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import type { TokenPair } from "../entities/auth";
import { tokenStorage } from "./tokenStorage";

type RetryableRequest = InternalAxiosRequestConfig & { _retry?: boolean };

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshRequest: Promise<TokenPair> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryableRequest | undefined;
    const refreshToken = tokenStorage.getRefreshToken();
    const isAuthEndpoint = request?.url?.startsWith("/auth/");
    if (error.response?.status !== 401 || !request || request._retry || isAuthEndpoint) {
      throw error;
    }
    if (!refreshToken) {
      tokenStorage.clear();
      throw error;
    }
    request._retry = true;
    refreshRequest ??= axios
      .post<TokenPair>("/api/auth/refresh", { refresh_token: refreshToken })
      .then((response) => response.data)
      .finally(() => {
        refreshRequest = null;
      });
    try {
      const tokens = await refreshRequest;
      tokenStorage.save(tokens);
      request.headers.Authorization = `Bearer ${tokens.access_token}`;
      return await apiClient(request);
    } catch (refreshError) {
      tokenStorage.clear();
      throw refreshError;
    }
  },
);

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? fallback;
  }
  return fallback;
}
