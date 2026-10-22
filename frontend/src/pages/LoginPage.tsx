import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Lock, Mail, AlertCircle, CheckCircle2 } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";

export const LoginPage: React.FC = () => {
  const { signIn, resetPasswordForEmail, status } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isResetMode, setIsResetMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null);

  // Field validation states
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  const validate = (): boolean => {
    let valid = true;
    setEmailError(null);
    setPasswordError(null);

    if (!email || !email.includes("@")) {
      setEmailError("Please enter a valid email address.");
      valid = false;
    }

    if (!isResetMode && (!password || password.length < 6)) {
      setPasswordError("Password must be at least 6 characters.");
      valid = false;
    }

    return valid;
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setErrorMessage(null);

    const { error } = await signIn(email, password);
    setLoading(false);

    if (error) {
      setErrorMessage("Invalid email or password. Please verify your credentials.");
    } else {
      navigate(from, { replace: true });
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes("@")) {
      setEmailError("Please enter a valid email address.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setResetSuccessMessage(null);

    const { error } = await resetPasswordForEmail(email);
    setLoading(false);

    if (error) {
      setErrorMessage(error);
    } else {
      setResetSuccessMessage(
        "If an account with this email exists, a password reset link has been sent."
      );
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-card bg-accent text-white shadow-lg mb-4">
            <span className="font-bold text-xl tracking-wider">E</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Edge<span className="text-accent">Ergo</span> Dashboard
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Privacy-Preserving Ergonomic Assessment Platform
          </p>
        </div>

        {/* Auth Card */}
        <Card className="p-6 sm:p-8 bg-surface border-border shadow-2xl">
          {status === "expired" && (
            <div
              role="alert"
              className="mb-6 p-3.5 rounded-control bg-warning/10 border border-warning/30 text-warning text-xs sm:text-sm flex items-start gap-2.5"
            >
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span>Your session has expired. Please sign in again to continue.</span>
            </div>
          )}

          {errorMessage && (
            <div
              role="alert"
              className="mb-6 p-3.5 rounded-control bg-danger/10 border border-danger/30 text-danger text-xs sm:text-sm flex items-start gap-2.5"
            >
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {resetSuccessMessage && (
            <div
              role="status"
              className="mb-6 p-3.5 rounded-control bg-success/10 border border-success/30 text-success text-xs sm:text-sm flex items-start gap-2.5"
            >
              <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
              <span>{resetSuccessMessage}</span>
            </div>
          )}

          {!isResetMode ? (
            <form onSubmit={handleSignIn} className="space-y-4" noValidate>
              <Input
                label="Email address"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={emailError ?? undefined}
                placeholder="name@company.com"
                icon={<Mail className="w-4 h-4" />}
              />

              <Input
                label="Password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={passwordError ?? undefined}
                placeholder="••••••••••••"
                icon={<Lock className="w-4 h-4" />}
              />

              <div className="flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setIsResetMode(true);
                    setErrorMessage(null);
                  }}
                  className="text-xs text-accent hover:underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none rounded px-1 min-h-[32px]"
                >
                  Forgot password?
                </button>
              </div>

              <Button type="submit" loading={loading} className="w-full mt-2" size="lg">
                Sign in to Dashboard
              </Button>
            </form>
          ) : (
            <form onSubmit={handleResetPassword} className="space-y-4" noValidate>
              <p className="text-xs text-text-secondary mb-4 leading-relaxed">
                Enter your account email to receive a secure password recovery link.
              </p>

              <Input
                label="Email address"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={emailError ?? undefined}
                placeholder="name@company.com"
                icon={<Mail className="w-4 h-4" />}
              />

              <Button type="submit" loading={loading} className="w-full mt-2" size="lg">
                Send Reset Link
              </Button>

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsResetMode(false);
                    setErrorMessage(null);
                    setResetSuccessMessage(null);
                  }}
                  className="text-xs text-text-muted hover:text-text-primary underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none rounded px-2 min-h-[44px]"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          )}
        </Card>

        {/* Privacy badge below card */}
        <p className="text-center text-xs text-text-muted mt-6">
          Zero raw video or facial biometric data is stored or transmitted by EdgeErgo.
        </p>
      </div>
    </div>
  );
};
