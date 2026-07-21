import type { LoginInput, RegisterInput, TokenPair, User } from "../../entities/auth";
import { apiClient } from "../../shared/apiClient";

export const authApi = {
  login: async (input: LoginInput) =>
    (await apiClient.post<TokenPair>("/auth/login", input)).data,
  register: async (input: RegisterInput) =>
    (await apiClient.post<TokenPair>("/auth/register", input)).data,
  me: async () => (await apiClient.get<User>("/auth/me")).data,
  logout: async (refreshToken: string) => {
    await apiClient.post("/auth/logout", { refresh_token: refreshToken });
  },
};
