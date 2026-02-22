/**
 * useStrategies — fetches strategy list once on mount.
 */
import { useState, useEffect } from "react";
import { api } from "../services/api";

export function useStrategies() {
  const [strategies, setStrategies] = useState([]);
  const [loading,    setLoading]    = useState(true);

  useEffect(() => {
    api.strategies()
      .then(setStrategies)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return { strategies, loading };
}
