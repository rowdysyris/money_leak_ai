import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json"
  }
});

/**
 * Emit a browser event that the toast provider can display.
 */
export function emitToast(detail) {
  window.dispatchEvent(new CustomEvent("moneyleak:toast", { detail }));
}

/**
 * Attach a bearer token from localStorage to outgoing requests when present.
 */
function attachAuthorizationHeader(config) {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}

/**
 * Forward request setup errors to axios callers.
 */
function handleRequestError(error) {
  return Promise.reject(error);
}

/**
 * Return successful responses without modification.
 */
function handleSuccessfulResponse(response) {
  if (response?.data && typeof response.data === "object" && "success" in response.data && response.data.success !== true) {
    return Promise.reject({ response });
  }
  return response;
}

/**
 * Convert an API or network failure into a user-safe message.
 */
export function getFriendlyErrorMessage(error) {
  if (error?.code === "ECONNABORTED") {
    return "The request took too long. Please try again.";
  }
  if (!error?.response) {
    return "Could not connect to server. Check your internet connection.";
  }
  if (error.response.status === 401) {
    return "Session expired. Please log in again.";
  }
  if (error.response.status === 403) {
    return "Access denied. You do not have permission to view this data.";
  }
  if (error.response.status >= 500) {
    return "Something went wrong. Please try again.";
  }
  return "Request could not be completed. Please check the details and try again.";
}

/**
 * Clear local auth state and redirect users after unauthorized API responses.
 */
function handleResponseError(error) {
  if (error?.response?.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_user");
    emitToast({ type: "error", message: "Session expired. Please log in again." });
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }
  if (error?.response?.status === 403) {
    emitToast({ type: "error", message: "Access denied. You do not have permission to view this data." });
  }
  return Promise.reject(error);
}

apiClient.interceptors.request.use(attachAuthorizationHeader, handleRequestError);
apiClient.interceptors.response.use(handleSuccessfulResponse, handleResponseError);

export default apiClient;
