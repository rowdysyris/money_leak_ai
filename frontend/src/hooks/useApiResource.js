import { useCallback, useEffect, useState } from "react";
import apiClient, { getFriendlyErrorMessage } from "../api/client";

/**
 * Fetch a GET endpoint and keep loading/error/warning state.
 */
export default function useApiResource(endpoint, options = {}) {
  const enabled = options.enabled ?? true;
  const initialData = options.initialData ?? null;
  const [data, setData] = useState(initialData);
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(Boolean(enabled));
  const [error, setError] = useState("");

  const fetchResource = useCallback(async function fetchResource() {
    if (enabled === false) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.get(endpoint);
      setData(response?.data?.data ?? null);
      setWarnings(response?.data?.warnings ?? []);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
      setData(initialData);
      setWarnings([]);
    } finally {
      setLoading(false);
    }
  }, [endpoint, enabled]);

  useEffect(function loadOnMount() {
    fetchResource();
  }, [fetchResource]);

  return { data, warnings, loading, error, refetch: fetchResource, setData };
}
