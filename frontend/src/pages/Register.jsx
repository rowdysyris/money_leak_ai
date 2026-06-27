import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getFriendlyErrorMessage } from "../api/client";
import AuthShell from "../components/AuthShell";
import { useAuth } from "../context/AuthContext";
import { PROFILE_TYPES } from "../constants/categories";
import { useToast } from "../components/ui/Toast";

/**
 * Render the registration screen.
 */
export default function Register() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profileType, setProfileType] = useState("Student");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  /**
   * Submit registration details to the API.
   */
  async function handleRegister() {
    setLoading(true);
    try {
      await register({ email, password, full_name: fullName, profile_type: profileType, city: city || null });
      showToast({ type: "success", message: "Account created successfully." });
      navigate("/upload");
    } catch (error) {
      showToast({ type: "error", message: getFriendlyErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="NEW ANALYSIS PROFILE"
      title="Build your money diagnosis."
      subtitle="Create a private profile, then upload a CSV or Excel statement export."
      footer={<p>Already registered? <Link to="/login">Log in</Link></p>}
    >
        <div className="auth-form mt-7 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-bold text-slate-700 sm:col-span-2">Full name
            <input value={fullName} onChange={(event) => setFullName(event.target.value)} className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500" />
          </label>
          <label className="block text-sm font-bold text-slate-700 sm:col-span-2">Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500" />
          </label>
          <label className="block text-sm font-bold text-slate-700 sm:col-span-2">Password
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500" />
          </label>
          <label className="block text-sm font-bold text-slate-700">Profile
            <select value={profileType} onChange={(event) => setProfileType(event.target.value)} className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500">
              {PROFILE_TYPES.map((profile) => <option key={profile} value={profile}>{profile}</option>)}
            </select>
          </label>
          <label className="block text-sm font-bold text-slate-700">City optional
            <input value={city} onChange={(event) => setCity(event.target.value)} className="mt-2 w-full border border-slate-200 px-4 py-3 outline-none focus:border-blue-500" placeholder="Bhopal" />
          </label>
          <button type="button" onClick={handleRegister} disabled={loading} className="signal-button w-full justify-center px-4 py-3.5 font-black text-white disabled:cursor-not-allowed disabled:opacity-60 sm:col-span-2">
            {loading ? "Creating account..." : "Get Started Free"}
          </button>
        </div>
    </AuthShell>
  );
}
