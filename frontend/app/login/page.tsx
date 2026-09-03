import { LoginForm } from "@/features/auth/login-form";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-16">
      <LoginForm />
    </main>
  );
}
