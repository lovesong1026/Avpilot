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

export async function refreshTokens(): Promise<TokenPair> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) throw new Error("登录状态已失效");
  refreshRequest ??= axios
    .post<TokenPair>("/api/auth/refresh", { refresh_token: refreshToken })
    .then((response) => response.data)
    .finally(() => {
      refreshRequest = null;
    });
  const tokens = await refreshRequest;
  tokenStorage.save(tokens);
  return tokens;
}

export async function authorizedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const request = (accessToken: string | null) =>
    fetch(input, {
      ...init,
      headers: {
        ...Object.fromEntries(new Headers(init.headers).entries()),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
    });
  let response = await request(tokenStorage.getAccessToken());
  if (response.status !== 401) return response;
  try {
    const tokens = await refreshTokens();
    response = await request(tokens.access_token);
    return response;
  } catch (error) {
    tokenStorage.clear();
    throw error;
  }
}

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
    try {
      const tokens = await refreshTokens();
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
