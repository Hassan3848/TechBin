import React, { useEffect, useMemo, useState } from "react";
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Camera,
  Radio,
  Wifi,
  Zap,
} from "lucide-react";
import {
  collection,
  onSnapshot,
  orderBy,
  query,
  where,
} from "firebase/firestore";
import { db } from "../../../firebase";
import { useAuth } from "../../contexts/AuthContext";

type BinStatus = "Active" | "Maintenance" | "Inactive";

type BinDoc = {
  orgId: string;
  binCode: string;
  location: string;
  status: BinStatus;
  capacityLiters?: number | null;
  createdAt?: any;
  createdBy?: string | null;
  updatedAt?: any;
  updatedBy?: string | null;
};

interface SensorStatus {
  name: string;
  status: "OK" | "Fault" | "Degraded";
  icon: React.ElementType;
  lastChecked: string;
  details: string;
}

interface BinHealth {
  binId: string;
  location: string;
  overallStatus: "Healthy" | "Warning" | "Critical";
  sensors: SensorStatus[];
}

// Small deterministic helper so the mock looks stable per bin
function stableHash(input: string) {
  let h = 0;
  for (let i = 0; i < input.length; i++) {
    h = (h * 31 + input.charCodeAt(i)) >>> 0;
  }
  return h;
}

function makeMockSensors(bin: BinDoc): SensorStatus[] {
  const seed = stableHash(`${bin.orgId}_${bin.binCode}`);
  const pick = (mod: number) => seed % mod;

  // Base: all OK
  const sensors: SensorStatus[] = [
    {
      name: "IR Sensor",
      status: "OK",
      icon: Radio,
      lastChecked: "2 min ago",
      details: "Operating normally",
    },
    {
      name: "Ultrasonic Sensor",
      status: "OK",
      icon: Radio,
      lastChecked: "2 min ago",
      details: "Capacity tracking normal",
    },
    {
      name: "Metal Sensor",
      status: "OK",
      icon: Zap,
      lastChecked: "2 min ago",
      details: "Calibrated",
    },
    {
      name: "Camera",
      status: "OK",
      icon: Camera,
      lastChecked: "1 min ago",
      details: "Image quality: Good",
    },
    {
      name: "Network",
      status: "OK",
      icon: Wifi,
      lastChecked: "30 sec ago",
      details: "Signal strength: 90%",
    },
  ];

  // Now adjust based on bin.status (your partial implementation logic)
  if (bin.status === "Maintenance") {
    // 1-2 degraded sensors
    sensors[pick(5)].status = "Degraded";
    sensors[pick(3)].details = "Requires calibration";
    sensors[4].status = "Degraded";
    sensors[4].details = "Signal strength: 65%";
  }

  if (bin.status === "Inactive") {
    // at least one fault
    sensors[3].status = "Fault";
    sensors[3].details = "Module not responding";
    sensors[3].lastChecked = "45 min ago";

    sensors[4].status = "Degraded";
    sensors[4].details = "No heartbeat packets";
    sensors[4].lastChecked = "12 min ago";
  }

  // Make ultrasonic show a “capacity %” mock if capacityLiters exists
  if (bin.capacityLiters != null) {
    const percent = 20 + (pick(60)); // 20..79
    sensors[1].details = `Capacity: ${percent}%`;
  } else {
    const percent = 30 + (pick(50)); // 30..79
    sensors[1].details = `Capacity: ${percent}% (mock)`;
  }

  return sensors;
}

function computeOverallStatus(bin: BinDoc, sensors: SensorStatus[]): "Healthy" | "Warning" | "Critical" {
  if (bin.status === "Inactive") return "Critical";
  if (bin.status === "Maintenance") return "Warning";

  const hasFault = sensors.some((s) => s.status === "Fault");
  if (hasFault) return "Critical";

  const hasDegraded = sensors.some((s) => s.status === "Degraded");
  if (hasDegraded) return "Warning";

  return "Healthy";
}

export const BinHealthStatusPage: React.FC = () => {
  const { user } = useAuth();

  const isSignedIn = !!user;
  const isSuperAdmin = user?.superAdmin === true;

  const myOrgId = user?.orgId?.trim()
    ? user.orgId.trim().toLowerCase()
    : "techbin";

  const [bins, setBins] = useState<Array<{ id: string } & BinDoc>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isSignedIn || !user) {
      setBins([]);
      setLoading(false);
      return;
    }

    setLoading(true);

    const base = collection(db, "bins");

    // IMPORTANT:
    // Non-superadmin MUST query only their org, otherwise Firestore rules can reject the query.
    const q = isSuperAdmin
      ? query(base, orderBy("createdAt", "desc"))
      : query(base, where("orgId", "==", myOrgId), orderBy("createdAt", "desc"));

    const unsub = onSnapshot(
      q,
      (snap) => {
        const rows = snap.docs.map((d) => ({ id: d.id, ...(d.data() as BinDoc) }));
        setBins(rows);
        setLoading(false);
      },
      (err) => {
        console.error("BinHealthStatusPage onSnapshot error:", err);
        setLoading(false);
        alert("Failed to load bins for health status (check rules/index).");
      }
    );

    return () => unsub();
  }, [isSignedIn, isSuperAdmin, myOrgId, user]);

  const binHealth: BinHealth[] = useMemo(() => {
    return bins.map((b) => {
      const sensors = makeMockSensors(b);
      const overallStatus = computeOverallStatus(b, sensors);

      return {
        binId: b.binCode,
        location: b.location,
        overallStatus,
        sensors,
      };
    });
  }, [bins]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "OK":
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case "Fault":
        return <XCircle className="w-5 h-5 text-red-600" />;
      case "Degraded":
        return <AlertCircle className="w-5 h-5 text-yellow-600" />;
      default:
        return null;
    }
  };

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case "Healthy":
        return "border-green-200 bg-gradient-to-br from-green-50 to-white";
      case "Warning":
        return "border-yellow-200 bg-gradient-to-br from-yellow-50 to-white";
      case "Critical":
        return "border-red-200 bg-gradient-to-br from-red-50 to-white";
      default:
        return "border-gray-200 bg-white";
    }
  };

  const getOverallStatusBadge = (status: string) => {
    switch (status) {
      case "Healthy":
        return "bg-green-100 text-green-800";
      case "Warning":
        return "bg-yellow-100 text-yellow-800";
      case "Critical":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const healthyCount = binHealth.filter((b) => b.overallStatus === "Healthy").length;
  const warningCount = binHealth.filter((b) => b.overallStatus === "Warning").length;
  const criticalCount = binHealth.filter((b) => b.overallStatus === "Critical").length;

  if (!isSignedIn) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h1 className="text-xl text-gray-900 mb-2">Bin Health Status</h1>
        <p className="text-gray-600">Please login to view bin health.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl text-gray-900 mb-2">Bin Health Status</h1>
        <p className="text-gray-600">
          {isSuperAdmin
            ? "System-wide sensor health monitoring (all orgs)"
            : `Sensor health monitoring (Org: ${myOrgId})`}
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-green-50 to-white rounded-xl shadow-sm p-6 border border-green-100">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-7 h-7 text-green-600" />
            </div>
            <div>
              <p className="text-3xl text-green-600">{healthyCount}</p>
              <p className="text-sm text-gray-600">Healthy Bins</p>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-yellow-50 to-white rounded-xl shadow-sm p-6 border border-yellow-100">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-7 h-7 text-yellow-600" />
            </div>
            <div>
              <p className="text-3xl text-yellow-600">{warningCount}</p>
              <p className="text-sm text-gray-600">Warning State</p>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-red-50 to-white rounded-xl shadow-sm p-6 border border-red-100">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <XCircle className="w-7 h-7 text-red-600" />
            </div>
            <div>
              <p className="text-3xl text-red-600">{criticalCount}</p>
              <p className="text-sm text-gray-600">Critical State</p>
            </div>
          </div>
        </div>
      </div>

      {/* Cards */}
      <div className="space-y-6">
        {loading ? (
          <div className="text-gray-600">Loading bins...</div>
        ) : binHealth.length === 0 ? (
          <div className="text-gray-600">No bins found.</div>
        ) : (
          binHealth.map((bin) => (
            <div
              key={bin.binId}
              className={`rounded-xl shadow-sm p-6 border-2 ${getOverallStatusColor(
                bin.overallStatus
              )}`}
            >
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-xl text-gray-900">{bin.binId}</h2>
                    <span
                      className={`px-3 py-1 rounded-full text-xs ${getOverallStatusBadge(
                        bin.overallStatus
                      )}`}
                    >
                      {bin.overallStatus}
                    </span>
                  </div>
                  <p className="text-gray-600">{bin.location}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                {bin.sensors.map((sensor, index) => {
                  const IconComponent = sensor.icon;
                  return (
                    <div
                      key={index}
                      className="bg-white rounded-lg p-4 border border-gray-200"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <IconComponent className="w-5 h-5 text-gray-600" />
                          <span className="text-sm text-gray-900">{sensor.name}</span>
                        </div>
                        {getStatusIcon(sensor.status)}
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-gray-500">{sensor.details}</p>
                        <p className="text-xs text-gray-400">{sensor.lastChecked}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
