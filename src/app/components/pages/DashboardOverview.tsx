import React, { useEffect, useState } from 'react';
import { TrendingUp, Recycle, Trash2, CheckCircle, Activity } from 'lucide-react';
import {
  LineChart, Line, PieChart, Pie, Cell,
  ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import {
  collection, onSnapshot, query, where,
  orderBy, Timestamp,
} from 'firebase/firestore';
import { db } from '../../../firebase';
import { useAuth } from '../../contexts/AuthContext';

type TelemetryDoc = {
  orgId: string;
  binCode: string;
  timestamp: Timestamp | null;
  wasteType: string;
  recyclable: boolean;
  confidence: number;
  disposalCorrect: boolean;
};

type BinDoc = {
  orgId: string;
  binCode: string;
  status: 'Active' | 'Maintenance' | 'Inactive';
};

// Group telemetry by hour for the line chart
function buildHourlyTrend(docs: TelemetryDoc[]) {
  const hours: Record<string, number> = {};
  for (let h = 0; h < 24; h += 4) {
    hours[`${String(h).padStart(2, '0')}:00`] = 0;
  }

  docs.forEach((d) => {
    if (!d.timestamp) return;
    const date = d.timestamp instanceof Timestamp ? d.timestamp.toDate() : new Date();
    const h = date.getHours();
    const bucket = `${String(Math.floor(h / 4) * 4).padStart(2, '0')}:00`;
    if (bucket in hours) hours[bucket]++;
  });

  return Object.entries(hours).map(([time, items]) => ({ time, items }));
}

export const DashboardOverview: React.FC = () => {
  const { user } = useAuth();
  const isSuperAdmin = user?.superAdmin === true;
  const myOrgId = user?.orgId?.trim() ? user.orgId.trim().toLowerCase() : 'techbin';

  // Today's telemetry
  const [telemetry, setTelemetry] = useState<TelemetryDoc[]>([]);
  // All bins
  const [bins, setBins] = useState<BinDoc[]>([]);
  const [loading, setLoading] = useState(true);

  // Subscribe to telemetry (all available data)
  useEffect(() => {
    if (!user) return;

    const base = collection(db, 'telemetry');
    const q = isSuperAdmin
      ? query(base, orderBy('timestamp', 'desc'))
      : query(
          base,
          where('orgId', '==', myOrgId),
          orderBy('timestamp', 'desc')
        );

    const unsub = onSnapshot(q, (snap) => {
      setTelemetry(snap.docs.map((d) => d.data() as TelemetryDoc));
      setLoading(false);
    }, (err) => {
      console.error('telemetry snapshot error:', err);
      setLoading(false);
    });

    return () => unsub();
  }, [user, isSuperAdmin, myOrgId]);

  // Subscribe to bins
  useEffect(() => {
    if (!user) return;

    const base = collection(db, 'bins');
    const q = isSuperAdmin
      ? query(base)
      : query(base, where('orgId', '==', myOrgId));

    const unsub = onSnapshot(q, (snap) => {
      setBins(snap.docs.map((d) => d.data() as BinDoc));
    }, (err) => {
      console.error('bins snapshot error:', err);
    });

    return () => unsub();
  }, [user, isSuperAdmin, myOrgId]);

  // Computed stats
  const totalItems = telemetry.length;
  const recyclableItems = telemetry.filter((t) => t.recyclable).length;
  const correctDisposals = telemetry.filter((t) => t.disposalCorrect).length;
  const correctRate = totalItems > 0 ? ((correctDisposals / totalItems) * 100).toFixed(1) : '0.0';
  const recyclablePct = totalItems > 0 ? ((recyclableItems / totalItems) * 100).toFixed(0) : '0';

  const totalBins = bins.length;
  const activeBins = bins.filter((b) => b.status === 'Active').length;
  const binPct = totalBins > 0 ? ((activeBins / totalBins) * 100).toFixed(0) : '0';

  const nonRecyclable = totalItems - recyclableItems;

  const dailyData = buildHourlyTrend(telemetry);

  const recyclabilityData = [
    { name: 'Recyclable', value: recyclableItems, color: '#10b981' },
    { name: 'Non-Recyclable', value: nonRecyclable, color: '#ef4444' },
  ];

  const stats = [
    {
      title: 'Total Waste Items Today',
      value: totalItems.toLocaleString(),
      icon: Trash2,
      bgColor: 'bg-blue-50',
      iconColor: 'text-blue-600',
    },
    {
      title: 'Recyclable Items',
      value: recyclableItems.toLocaleString(),
      percentage: `${recyclablePct}%`,
      icon: Recycle,
      bgColor: 'bg-emerald-50',
      iconColor: 'text-emerald-600',
    },
    {
      title: 'Correct Disposal Rate',
      value: `${correctRate}%`,
      icon: CheckCircle,
      bgColor: 'bg-green-50',
      iconColor: 'text-green-600',
    },
    {
      title: 'Active Bins',
      value: `${activeBins}/${totalBins}`,
      percentage: `${binPct}%`,
      icon: Activity,
      bgColor: 'bg-gray-50',
      iconColor: 'text-gray-600',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl text-gray-900 mb-2">Dashboard Overview</h1>
        <p className="text-gray-600">
          Monitoring and analytics summary — all time
          {loading && <span className="ml-2 text-xs text-gray-400">(loading...)</span>}
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <div key={index} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <div className="flex items-start justify-between mb-4">
              <div className={`w-12 h-12 rounded-lg ${stat.bgColor} flex items-center justify-center`}>
                <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
              </div>
              <TrendingUp className="w-4 h-4 text-green-500 mt-1" />
            </div>
            <h3 className="text-2xl text-gray-900 mb-1">{stat.value}</h3>
            <p className="text-sm text-gray-600">{stat.title}</p>
            {stat.percentage && (
              <p className="text-xs text-emerald-600 mt-2">{stat.percentage} of total</p>
            )}
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Disposal Trend */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4">Today's Disposal Trend</h2>
          {totalItems === 0 && !loading ? (
            <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
              No telemetry data for today yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={dailyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="time" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="items"
                  stroke="#10b981"
                  strokeWidth={3}
                  dot={{ fill: '#10b981', r: 4 }}
                  name="Waste Items"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recyclability Distribution */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4">Recyclability Distribution</h2>
          {totalItems === 0 && !loading ? (
            <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
              No telemetry data for today yet.
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={recyclabilityData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100}
                    dataKey="value"
                  >
                    {recyclabilityData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-6 mt-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-emerald-600 rounded-full" />
                  <span className="text-sm text-gray-600">Recyclable: {recyclableItems}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-red-500 rounded-full" />
                  <span className="text-sm text-gray-600">Non-Recyclable: {nonRecyclable}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
