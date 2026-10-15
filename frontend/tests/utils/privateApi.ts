// Note: the `PrivateService` is only available when generating the client
// for local environments
import { OpenAPI, PrivateService, type Role } from "../../src/client"

OpenAPI.BASE = `${process.env.VITE_API_URL}`

export const createUser = async ({
  email,
  password,
  role,
}: {
  email: string
  password: string
  role?: Role
}) => {
  return await PrivateService.createUser({
    requestBody: {
      email,
      password,
      is_verified: true,
      full_name: "Test User",
      role,
    },
  })
}
