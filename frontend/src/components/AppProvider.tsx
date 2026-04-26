import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { APP_BASE_PATH } from "app";

interface Props {
  children: ReactNode;
}

/**
 * A provider wrapping the whole app.
 *
 * You can add multiple providers here by nesting them,
 * and they will all be applied to the app.
 */
export const AppProvider = ({ children }: Props) => {
  // When the app loads, add diagnostic info to the console
  console.log(`App initialized with base path: ${APP_BASE_PATH}`);
  console.log(`Current location: ${window.location.href}`);
  console.log(`Current pathname: ${window.location.pathname}`);
  
  return (
    <>
      {children}
      <Toaster position="top-center" />
    </>
  );
};