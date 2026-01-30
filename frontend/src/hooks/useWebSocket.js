// src/hooks/useWebSocket.js
import { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';

const DEFAULT_OPTS = {
  transports: ['websocket'], // prefer websocket transport
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 5
};

export default function useWebSocket(apiUrl) {
  const socketRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [priceUpdates, setPriceUpdates] = useState({});

  // keep a stable ref to apiUrl so effect re-runs only when necessary
  const urlRef = useRef(apiUrl);
  useEffect(() => { urlRef.current = apiUrl; }, [apiUrl]);

  useEffect(() => {
    const endpoint = urlRef.current;
    const socket = io(endpoint, DEFAULT_OPTS);
    socketRef.current = socket;

    const onConnect = () => {
      console.info('WebSocket connected');
      setIsConnected(true);
    };
    const onDisconnect = (reason) => {
      console.info('WebSocket disconnected', reason);
      setIsConnected(false);
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);

    // price_update handler: only apply changes when meaningful difference detected
    socket.on('price_update', (data) => {
      try {
        if (!data || !data.ticker) return;
        const key = data.ticker;
        const incoming = {
          price: data.price != null ? Number(data.price) : null,
          change: data.change ?? null,
          change_percent: data.change_percent ?? null,
          ts: data.ts ?? Date.now()
        };

        setPriceUpdates(prev => {
          const prevEntry = prev[key];
          // numeric comparison epsilon
          const EPS = 1e-6;

          const prevPrice = prevEntry && prevEntry.price != null ? Number(prevEntry.price) : NaN;
          const incomingPrice = Number(incoming.price);

          const priceChanged = Number.isFinite(incomingPrice) && Math.abs(incomingPrice - (Number(prevPrice) || 0)) > EPS;
          const changeChanged = incoming.change !== prevEntry?.change;
          const pctChanged = incoming.change_percent !== prevEntry?.change_percent;

          if (!priceChanged && !changeChanged && !pctChanged) {
            // nothing meaningful changed -> return same object (no re-render)
            return prev;
          }

          // apply update
          const next = { ...prev, [key]: incoming };
          console.debug('useWebSocket: applied price_update', key, incoming);
          return next;
        });
      } catch (e) {
        console.warn('useWebSocket - price_update handler error', e);
      }
    });

    socket.on('connect_error', (err) => {
      console.warn('WebSocket connect_error', err?.message ?? err);
    });

    // cleanup
    return () => {
      try {
        if (socketRef.current) {
          socketRef.current.off('connect', onConnect);
          socketRef.current.off('disconnect', onDisconnect);
          socketRef.current.off('price_update');
          socketRef.current.disconnect();
        }
      } catch (e) {
        /* ignore cleanup errors */
      }
      socketRef.current = null;
    };
  }, []); // run once

  // stable emit functions
  const trackStock = useCallback((ticker) => {
    const s = socketRef.current;
    if (!s || !ticker) return;
    try {
      s.emit('track_stock', { ticker });
    } catch (e) {
      console.warn('trackStock emit failed', e);
    }
  }, []);

  const untrackStock = useCallback((ticker) => {
    const s = socketRef.current;
    if (!s || !ticker) return;
    try {
      s.emit('untrack_stock', { ticker });
    } catch (e) {
      console.warn('untrackStock emit failed', e);
    }
  }, []);

  return { isConnected, priceUpdates, trackStock, untrackStock };
}
