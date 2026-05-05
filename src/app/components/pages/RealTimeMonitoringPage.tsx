import React, { useEffect, useMemo, useState } from "react";
import { RefreshCw, CheckCircle, XCircle, Clock, Database, Play } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import {
  addDoc,
  collection,
  getDocs,
  limit,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  where,
  Timestamp,
} from "firebase/firestore";
import { db } from "../../../firebase";
import { useAuth } from "../../contexts/AuthContext";
import { useSettings } from "../../contexts/SettingsContext";

type BinStatus = "Active" | "Maintenance" | "Inactive";

type BinDoc = {
  orgId: string;
  // NEW schema
  binCode?: string;
  // OLD schema fallback
  code?: string;

  location: string;
  status: BinStatus;
};

type TelemetryDoc = {
  orgId: string;
  binCode: string;
  timestamp: any; // Firestore Timestamp
  wasteType: string;
  recyclable: boolean;
  confidence: number; // 0-100
  disposalCorrect: boolean;
};

const WASTE_TYPES = ["Plastic Bottle", "Paper Cup", "Aluminum Can", "Food Waste", "Glass Bottle"];

function randomFrom<T>(arr: T[]) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function getBinCode(b: BinDoc) {
  return (b.binCode || b.code || "").trim().toUpperCase();
}

function formatTs(ts: any) {
  try {
    if (!ts) return "-";
    if (ts instanceof Timestamp) return ts.toDate().toLocaleString();
    if (typeof ts?.toDate === "function") return ts.toDate().toLocaleString();
    return String(ts);
  } catch {
    return "-";
  }
}

export const RealTimeMonitoringPage: React.FC = () => {
  const { user } = useAuth();
  const { settings } = useSettings();
  const [params, setParams] = useSearchParams();

  const isSignedIn = !!user;

  // normalize org id exactly like Bin Registry does
  const myOrgId = user?.orgId?.trim() ? user.orgId.trim().toLowerCase() : "techbin";
  const isSuperAdmin = user?.superAdmin === true;

  // ---- bins dropdown ----
  const [bins, setBins] = useState<Array<{ id: string } & BinDoc>>([]);
  const [selectedBin, setSelectedBin] = useState<string>((params.get("bin") || "").trim().toUpperCase());
  const [binsLoading, setBinsLoading] = useState(true);

  // ---- telemetry feed ----
  const [telemetry, setTelemetry] = useState<Array<{ id: string } & TelemetryDoc>>([]);
  const [feedLoading, setFeedLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [busy, setBusy] = useState(false);
  const autoMockIntervalMs = Number(settings.refreshRate || "10") * 1000;

  // keep state ↔ url synced
  useEffect(() => {
    const qbin = (params.get("bin") || "").trim().toUpperCase();
    if (qbin && qbin !== selectedBin) setSelectedBin(qbin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const p = new URLSearchParams(params);
    if (!selectedBin) {
      p.delete("bin");
      setParams(p, { replace: true });
      return;
    }
    p.set("bin", selectedBin);
    setParams(p, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBin]);

  // load bins realtime (dropdown)
  useEffect(() => {
    if (!isSignedIn) {
      setBins([]);
      setBinsLoading(false);
      return;
    }

    setBinsLoading(true);
    const base = collection(db, "bins");

    const q = isSuperAdmin
      ? query(base, orderBy("createdAt", "desc"))
      : query(base, where("orgId", "==", myOrgId), orderBy("createdAt", "desc"));

    const unsub = onSnapshot(
      q,
      (snap) => {
        const rows = snap.docs.map((d) => ({ id: d.id, ...(d.data() as BinDoc) }));
        setBins(rows);
        setBinsLoading(false);

        // If current selection is missing (or empty), auto-pick the first valid bin
        const codes = rows.map(getBinCode).filter(Boolean);
        const selectionExists = selectedBin && codes.includes(selectedBin);

        if ((!selectedBin || !selectionExists) && codes.length > 0) {
          setSelectedBin(codes[0]);
        }
      },
      (err) => {
        console.error("bins snapshot error:", err);
        setBinsLoading(false);
        alert("Failed to load bins for Monitoring (check Firestore rules / indexes).");
      }
    );

    return () => unsub();
  }, [isSignedIn, isSuperAdmin, myOrgId, selectedBin]);

  const selectedBinMeta = useMemo(() => {
    return bins.find((b) => getBinCode(b) === selectedBin) || null;
  }, [bins, selectedBin]);

  // telemetry table refreshes at user-selected interval
  useEffect(() => {
    if (!isSignedIn || !selectedBin) {
      setTelemetry([]);
      return;
    }

    const base = collection(db, "telemetry");

    const q = isSuperAdmin
      ? query(base, where("binCode", "==", selectedBin), orderBy("timestamp", "desc"), limit(25))
      : query(
          base,
          where("orgId", "==", myOrgId),
          where("binCode", "==", selectedBin),
          orderBy("timestamp", "desc"),
          limit(25)
        );

    let active = true;
    const refreshMs = Number(settings.refreshRate || "10") * 1000;

    const loadTelemetry = async () => {
      setFeedLoading(true);
      try {
        const snap = await getDocs(q);
        if (!active) return;
        const rows = snap.docs.map((d) => ({ id: d.id, ...(d.data() as TelemetryDoc) }));
        setTelemetry(rows);
        setLastUpdate(new Date());
      } catch (err) {
        console.error("telemetry fetch error:", err);
        if (active) alert("Failed to load telemetry (rules or missing index).");
      } finally {
        if (active) setFeedLoading(false);
      }
    };

    loadTelemetry();
    const interval = setInterval(loadTelemetry, refreshMs);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [isSignedIn, isSuperAdmin, myOrgId, selectedBin, settings.refreshRate]);

  // optional “auto-mock”: generate 1 doc using Settings refresh interval
  useEffect(() => {
    if (!autoRefresh) return;
    if (!isSignedIn || !selectedBin) return;

    const interval = setInterval(async () => {
      try {
        const orgForDoc = isSuperAdmin ? (selectedBinMeta?.orgId || myOrgId) : myOrgId;

        await addDoc(collection(db, "telemetry"), {
          orgId: orgForDoc,
          binCode: selectedBin,
          timestamp: serverTimestamp(),
          wasteType: randomFrom(WASTE_TYPES),
          recyclable: Math.random() > 0.4,
          confidence: clamp(85 + Math.random() * 14, 0, 100),
          disposalCorrect: Math.random() > 0.15,
        } as TelemetryDoc);
      } catch (e) {
        console.error("auto mock telemetry failed:", e);
      }
    }, autoMockIntervalMs);

    return () => clearInterval(interval);
  }, [autoRefresh, isSignedIn, selectedBin, isSuperAdmin, myOrgId, selectedBinMeta, autoMockIntervalMs]);

  const generateMockBurst = async () => {
    if (!isSignedIn || !selectedBin) return;

    setBusy(true);
    try {
      const orgForDoc = isSuperAdmin ? (selectedBinMeta?.orgId || myOrgId) : myOrgId;

      const tasks = Array.from({ length: 10 }).map(() =>
        addDoc(collection(db, "telemetry"), {
          orgId: orgForDoc,
          binCode: selectedBin,
          timestamp: serverTimestamp(),
          wasteType: randomFrom(WASTE_TYPES),
          recyclable: Math.random() > 0.4,
          confidence: clamp(85 + Math.random() * 14, 0, 100),
          disposalCorrect: Math.random() > 0.15,
        } as TelemetryDoc)
      );

      await Promise.all(tasks);
      alert("✅ Mock telemetry generated (10 events).");
    } catch (e: any) {
      console.error(e);
      alert(e?.message || "Failed to generate mock telemetry.");
    } finally {
      setBusy(false);
    }
  };

  const showOrg = isSuperAdmin ? "Super Admin: can view telemetry for any org bin" : `Org: ${myOrgId}`;

  if (!isSignedIn) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h1 className="text-2xl text-gray-900 mb-2">Real-Time Monitoring</h1>
        <p className="text-gray-600">Please login to view monitoring.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-2xl text-gray-900 mb-1">Real-Time Monitoring</h1>
          <p className="text-gray-600">
            Live waste detection feed (Firestore: <b>telemetry</b>)
          </p>
          <p className="text-sm text-gray-500 mt-1">{showOrg}</p>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-700 rounded-lg">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Last update: {lastUpdate.toLocaleTimeString()}</span>
          </div>

          <div className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg">
            <span className="text-sm">Refresh interval: {settings.refreshRate}s</span>
          </div>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              autoRefresh ? "bg-emerald-600 text-white" : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${autoRefresh ? "animate-spin" : ""}`} />
            <span className="text-sm">{autoRefresh ? "Auto-mock On" : "Auto-mock Off"}</span>
          </button>

          <button
            onClick={generateMockBurst}
            disabled={busy || !selectedBin}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-black disabled:opacity-60"
            title="Write 10 mock telemetry docs into Firestore"
          >
            <Play className="w-4 h-4" />
            <span className="text-sm">{busy ? "Generating..." : "Generate Mock"}</span>
          </button>
        </div>
      </div>

      {/* Bin selector */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
        <div className="flex items-center gap-2 text-gray-700">
          <Database className="w-4 h-4 text-gray-400" />
          <span className="text-sm">Selected Bin</span>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
          <select
            className="min-w-[240px] px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-emerald-500 bg-white"
            value={selectedBin}
            onChange={(e) => setSelectedBin(e.target.value)}
            disabled={binsLoading}
          >
            {binsLoading ? (
              <option value="">Loading bins...</option>
            ) : bins.length === 0 ? (
              <option value="">No bins available</option>
            ) : (
              bins
                .map((b) => ({ b, code: getBinCode(b) }))
                .filter((x) => x.code)
                .map(({ b, code }) => (
                  <option key={b.id} value={code}>
                    {code} — {b.location}
                  </option>
                ))
            )}
          </select>

          {selectedBinMeta && (
            <div className="text-sm text-gray-600">
              <span className="font-medium text-gray-900">{selectedBinMeta.location}</span>{" "}
              <span className="text-gray-500">•</span>{" "}
              <span className="text-gray-700">{selectedBinMeta.status}</span>
              {isSuperAdmin && (
                <>
                  {" "}
                  <span className="text-gray-500">•</span>{" "}
                  <span className="text-gray-700">Org: {selectedBinMeta.orgId}</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Live Feed Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-xs text-gray-600 uppercase tracking-wider">Timestamp</th>
                <th className="px-6 py-4 text-left text-xs text-gray-600 uppercase tracking-wider">Bin Code</th>
                <th className="px-6 py-4 text-left text-xs text-gray-600 uppercase tracking-wider">Waste Type</th>
                <th className="px-6 py-4 text-left text-xs text-gray-600 uppercase tracking-wider">Recyclability</th>
                <th className="px-6 py-4 text-left text-xs text-gray-600 uppercase tracking-wider">Confidence</th>
                <th className="px-6 py-4 text-left text-xs text-gray-600 uppercase tracking-wider">Disposal Status</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-gray-100">
              {feedLoading ? (
                <tr>
                  <td className="px-6 py-5 text-sm text-gray-600" colSpan={6}>
                    Loading telemetry...
                  </td>
                </tr>
              ) : telemetry.length === 0 ? (
                <tr>
                  <td className="px-6 py-6 text-sm text-gray-600" colSpan={6}>
                    No telemetry found for <b>{selectedBin || "-"}</b>. Click <b>Generate Mock</b>.
                  </td>
                </tr>
              ) : (
                telemetry.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-700">{formatTs(t.timestamp)}</td>
                    <td className="px-6 py-4 text-sm text-gray-900 font-medium">{t.binCode}</td>
                    <td className="px-6 py-4 text-sm text-gray-700">{t.wasteType}</td>
                    <td className="px-6 py-4 text-sm">
                      <span
                        className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                          t.recyclable ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {t.recyclable ? "Recyclable" : "Non-Recyclable"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">{t.confidence.toFixed(1)}%</td>
                    <td className="px-6 py-4 text-sm">
                      <span
                        className={`inline-flex items-center gap-2 ${
                          t.disposalCorrect ? "text-emerald-700" : "text-rose-700"
                        }`}
                      >
                        {t.disposalCorrect ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                        {t.disposalCorrect ? "Correct" : "Incorrect"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border border-blue-200 bg-blue-50 text-blue-800 rounded-xl p-4 text-sm">
        <b>How it works:</b> This page listens to Firestore <b>telemetry</b> documents for the selected bin (
        <b>binCode</b>) and your org (<b>orgId</b>). Use <b>Generate Mock</b> to insert sample telemetry and watch the
        table update live.
      </div>
    </div>
  );
};

export default RealTimeMonitoringPage;
