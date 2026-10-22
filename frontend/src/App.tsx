import React from "react";
import { BrowserRouter } from "react-router-dom";
import { getMissingEnvConfig } from "./lib/supabase";
import { ConfigMissingScreen } from "./components/ui/ConfigMissingScreen";
import { AuthProvider } from "./features/auth/AuthContext";
import { UserProfileProvider } from "./features/auth/UserProfileContext";
import { ToastProvider } from "./components/ui/Toast";
import { AppRoutes } from "./AppRoutes";

import { DevFixtureProvider } from "./lib/devFixtures";

export function App(): React.JSX.Element {
  const missingConfig = getMissingEnvConfig();

  // If essential client configuration is absent, render explicit config screen
  if (missingConfig.length > 0) {
    return <ConfigMissingScreen missingKeys={missingConfig} />;
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <UserProfileProvider>
          <DevFixtureProvider>
            <ToastProvider>
              <AppRoutes />
            </ToastProvider>
          </DevFixtureProvider>
        </UserProfileProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
