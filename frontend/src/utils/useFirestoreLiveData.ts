/**
 * Firestore Live Data Hook
 * Real-time listener for cluster provisioning status from live_infrastructure collection
 */

import { useState, useEffect } from 'react';
import { getFirestore } from 'firebase/firestore';
import { collection, query, where, onSnapshot, DocumentData } from 'firebase/firestore';
import { firebaseApp } from '../app';

export interface SwitchStatus {
  switchId: string;
  deviceName: string;
  planeId: number;
  leafId: number;
  rackId: number;
  status: string;
  cablingHealthPercentage?: number;
  macAddress?: string;
  ipAddress?: string;
  tier?: string;
  suNumber?: number;
}

interface FabricHealth {
  total: number;
  operational: number;
  inProgress: number;
  errors: number;
  healthPercentage: number;
}

export function useFirestoreLiveData(suId?: string) {
  const [switches, setSwitches] = useState<SwitchStatus[]>([]);
  const [fabricHealth, setFabricHealth] = useState<FabricHealth>({
    total: 0,
    operational: 0,
    inProgress: 0,
    errors: 0,
    healthPercentage: 0
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!suId) {
      setSwitches([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    const firestore = getFirestore(firebaseApp);
    const switchesRef = collection(firestore, 'live_infrastructure');

    try {
      // Real-time listener on live_infrastructure collection
      const infraRef = collection(firestore, 'live_infrastructure');
      const q = query(infraRef, where('tier', '==', 'TIER_1')); // Leafs only

      const unsubscribe = onSnapshot(
        q,
        (snapshot) => {
          const switchData: SwitchStatus[] = [];
          
          snapshot.forEach((doc) => {
            const data = doc.data() as DocumentData;
            switchData.push({
              switchId: doc.id,
              deviceName: data.device_name || doc.id,
              planeId: data.plane_id ?? 0,
              leafId: data.leaf_id ?? 0,
              rackId: data.rack_id ?? 0,
              status: data.status || 'PLANNED',
              cablingHealthPercentage: data.cabling_health_percentage,
              macAddress: data.mac_address,
              ipAddress: data.ip_address,
              tier: data.tier,
              suNumber: data.su_number ?? 1
            });
          });

          setSwitches(switchData);
          
          // Calculate fabric health
          const total = switchData.length;
          const operational = switchData.filter(s => s.status === 'OPERATIONAL').length;
          const errors = switchData.filter(s => 
            s.status === 'ERROR' || 
            s.status === 'WIRING_ERROR' || 
            s.status === 'IDENTITY_MISMATCH' ||
            s.status === 'BLOCKED_IDENTITY_MISMATCH'
          ).length;
          const inProgress = switchData.filter(s => 
            s.status === 'DISCOVERY' ||
            s.status === 'DISCOVERY_VERIFIED' ||
            s.status === 'CONFIGURING' ||
            s.status === 'PROVISIONING' ||
            s.status === 'ZTP_IN_PROGRESS' ||
            s.status === 'VALIDATING' ||
            s.status === 'VALIDATING_CABLING'
          ).length;

          setFabricHealth({
            total,
            operational,
            inProgress,
            errors,
            healthPercentage: total > 0 ? (operational / total) * 100 : 0
          });

          setIsLoading(false);
        },
        (err) => {
          console.error('Firestore listener error:', err);
          setError(err.message);
          setIsLoading(false);
        }
      );

      // Cleanup listener on unmount
      return () => unsubscribe();
    } catch (err: any) {
      console.error('Failed to set up Firestore listener:', err);
      setError(err.message);
      setIsLoading(false);
    }
  }, []);

  const refreshData = () => {
    setIsLoading(true);
    // Firestore listener will auto-refresh
    setTimeout(() => setIsLoading(false), 500);
  };

  return {
    switches,
    fabricHealth,
    isLoading,
    error,
    refreshData
  };
}
