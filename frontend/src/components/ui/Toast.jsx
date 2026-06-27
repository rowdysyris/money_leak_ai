import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const ToastContext = createContext(null);

/**
 * Build a class string for a toast type.
 */
function toastClass(type) {
  if (type === "success") {
    return "toast-notice--success";
  }
  if (type === "error") {
    return "toast-notice--error";
  }
  return "toast-notice--info";
}

/**
 * Provide toast notifications to the app.
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback(function showToast(toast) {
    const id = `${Date.now()}-${Math.random()}`;
    const nextToast = { id, type: toast?.type ?? "info", message: toast?.message ?? "Done" };
    setToasts((items) => [...items, nextToast]);
    window.setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id));
    }, 3500);
  }, []);

  useEffect(function registerToastEventListener() {
    const listener = function listener(event) {
      showToast(event.detail ?? {});
    };
    window.addEventListener("moneyleak:toast", listener);
    return function cleanup() {
      window.removeEventListener("moneyleak:toast", listener);
    };
  }, [showToast]);

  const value = useMemo(function buildValue() {
    return { showToast };
  }, [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed right-4 top-4 z-50 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-3">
        {toasts.map((toast) => (
          <div key={toast.id} role="status" className={`toast-notice border px-4 py-3 text-sm font-semibold ${toastClass(toast.type)}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/**
 * Return the active toast API.
 */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used inside ToastProvider");
  }
  return context;
}
