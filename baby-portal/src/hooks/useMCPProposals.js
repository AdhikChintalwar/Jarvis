import {
    useEffect,
    useState,
  } from "react";
  
  
  export default function useMCPProposals() {
    const [proposals, setProposals] =
      useState([]);
  
    const [loading, setLoading] =
      useState(true);
  
    const [error, setError] =
      useState(null);
  
  
    useEffect(() => {
      let mounted = true;
  
      async function load() {
        try {
          const response = await fetch(
            `/mcp_proposals.json?t=${Date.now()}`
          );
  
          if (!response.ok) {
            throw new Error(
              `HTTP ${response.status}`
            );
          }
  
          const data =
            await response.json();
  
          if (
            mounted &&
            Array.isArray(data)
          ) {
            setProposals(data);
            setError(null);
          }
        } catch (err) {
          if (mounted) {
            setError(
              String(err)
            );
          }
        } finally {
          if (mounted) {
            setLoading(false);
          }
        }
      }
  
      load();
  
      const interval =
        setInterval(
          load,
          1500
        );
  
      return () => {
        mounted = false;
        clearInterval(interval);
      };
    }, []);
  
  
    return {
      proposals,
      loading,
      error,
    };
  }