import { APP_BASE_PATH } from "app";

/**
 * Utility functions for handling navigation paths consistently 
 * with base path prefix in production environment
 */

/**
 * Get a path that correctly works with base path prefix
 * @param path - Relative path without leading slash
 * @returns Path that works in both dev and production
 */
export function getRoutePath(path: string): string {
  // Strip any leading slashes
  const cleanPath = path.startsWith("/") ? path.substring(1) : path;
  
  console.log(`getRoutePath - Input: ${path}, APP_BASE_PATH: ${APP_BASE_PATH}`);
  
  // Add base path prefix if needed
  if (APP_BASE_PATH && APP_BASE_PATH !== "/") {
    // Ensure we don't have double slashes
    const basePath = APP_BASE_PATH.endsWith("/") ? APP_BASE_PATH.slice(0, -1) : APP_BASE_PATH;
    const result = `${basePath}/${cleanPath}`;
    console.log(`getRoutePath - Result with base path: ${result}`);
    return result;
  }
  
  const result = `/${cleanPath}`;
  console.log(`getRoutePath - Result without base path: ${result}`);
  return result;
}

/**
 * Navigate safely with base path consideration
 * @param path - Path to navigate to
 */
export function navigateSafely(path: string): void {
  const fullPath = getRoutePath(path);
  console.log(`navigateSafely - Redirecting to: ${fullPath}`);
  window.location.href = fullPath;
}
