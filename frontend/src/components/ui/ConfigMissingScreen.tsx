import React from "react";
import { AlertTriangle, KeyRound } from "lucide-react";
import { Card } from "./Card";

export interface ConfigMissingScreenProps {
  missingKeys: string[];
}

export const ConfigMissingScreen: React.FC<ConfigMissingScreenProps> = ({ missingKeys }) => {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-danger/40 bg-[#160f12] p-6 sm:p-8 text-center shadow-2xl">
        <div className="mx-auto w-12 h-12 rounded-full bg-danger/10 text-danger flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-semibold text-text-primary mb-2">Configuration Required</h1>
        <p className="text-sm text-text-secondary mb-6 leading-relaxed">
          EdgeErgo Web Dashboard could not start because required client environment variables are not configured.
        </p>

        <div className="bg-surface-raised border border-border rounded-control p-4 text-left mb-6">
          <span className="text-xs font-medium text-text-muted uppercase tracking-wider block mb-2 flex items-center gap-1.5">
            <KeyRound className="w-3.5 h-3.5 text-warning" /> Missing Variables
          </span>
          <ul className="space-y-1.5 text-xs font-mono text-warning">
            {missingKeys.map((key) => (
              <li key={key} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                {key}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-text-muted leading-normal">
          Please copy <code className="text-accent">.env.example</code> to <code className="text-accent">.env</code> in the <code className="text-text-secondary">frontend/</code> directory and provide your Supabase project URL and anon/publishable key.
        </p>
      </Card>
    </div>
  );
};
