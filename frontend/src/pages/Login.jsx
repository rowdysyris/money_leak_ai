import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getFriendlyErrorMessage } from "../api/client";
import AuthShell from "../components/AuthShell";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/ui/Toast";

/**
 * Render the login screen.
 */
export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  /**
   * Submit login credentials to the API.
   */
  async function handleLogin() {
    setLoading(true);
    try {
      await login({ email, password });
      showToast({ type: "success", message: "Logged in successfully." });
      navigate("/dashboard");
    } catch (error) {
      showToast({ type: "error", message: getFriendlyErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="ACCOUNT ACCESS"
      title="Return to your analysis."
      subtitle="Continue to your private financial dashboard and latest money diagnosis."
      footer={<p>New here? <Link to="/register">Create account</Link></p>}
    >
        <div className="auth-form mt-7 space-y-5">
          <label className="block text-sm font-bold text-slate-700">Email address
            <input value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500" placeholder="you@example.com" />
          </label>
          <label className="block text-sm font-bold text-slate-700">Password
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500" placeholder="Minimum 8 characters" />
          </label>
          <button type="button" onClick={handleLogin} disabled={loading} className="signal-button w-full justify-center px-4 py-3.5 font-black text-white disabled:cursor-not-allowed disabled:opacity-60">
            {loading ? "Logging in..." : "Login"}
          </button>
        </div>
    </AuthShell>
  );
}
