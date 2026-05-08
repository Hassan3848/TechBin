import React, { useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, LineChart, Line, ResponsiveContainer,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
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
  disposalCorrect: boolean;
};

type BinDoc = {
  orgId: string;
  binCode: string;
  status: string;
};

const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function buildDisposalTrend(docs: TelemetryDoc[]) {
  const today = new Date();
  const days: { date: string; correct: number; incorrect: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    days.push({ date: DAY_LABELS[d.getDay()], correct: 0, incorrect: 0 });
  }
  docs.forEach((doc) => {
    if (!doc.timestamp) return;
    const ts = doc.timestamp instanceof Timestamp ? doc.timestamp.toDate() : new Date();
    const diffDays = Math.floor((today.getTime() - ts.getTime()) / 86400000);
    if (diffDays < 0 || diffDays > 6) return;
    const idx = 6 - diffDays;
    if (doc.disposalCorrect) days[idx].correct++;
    else days[idx].incorrect++;
  });
  return days;
}

function buildWasteCategories(docs: TelemetryDoc[]) {
  const map: Record<string, { recyclable: number; nonRecyclable: number }> = {};
  docs.forEach((doc) => {
    const cat = doc.wasteType || 'Other';
    if (!map[cat]) map[cat] = { recyclable: 0, nonRecyclable: 0 };
    if (doc.recyclable) map[cat].recyclable++;
    else map[cat].nonRecyclable++;
  });
  return Object.entries(map)
    .map(([category, v]) => ({ category, ...v }))
    .sort((a, b) => (b.recyclable + b.nonRecyclable) - (a.recyclable + a.nonRecyclable));
}

export const AnalyticsPage: React.FC = () => {
  const { user } = useAuth();
  const isSuperAdmin = user?.superAdmin === true;
  const myOrgId = user?.orgId?.trim() ? user.orgId.trim().toLowerCase() : 'techbin';

  const [dateRange, setDateRange] = useState('all');
  const [selectedBin, setSelectedBin] = useState('all');
  const [telemetry, setTelemetry] = useState<TelemetryDoc[]>([]);
  const [bins, setBins] = useState<BinDoc[]>([]);
  const [loading, setLoading] = useState(true);

  const rangeStart = useMemo(() => {
    if (dateRange === 'all') return null;
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    if (dateRange === 'weekly') d.setDate(d.getDate() - 6);
    else if (dateRange === 'monthly') d.setDate(d.getDate() - 29);
    return Timestamp.fromDate(d);
  }, [dateRange]);

  // Bins dropdown
  useEffect(() => {
    if (!user) return;
    const base = collection(db, 'bins');
    const q = isSuperAdmin
      ? query(base, orderBy('createdAt', 'desc'))
      : query(base, where('orgId', '==', myOrgId), orderBy('createdAt', 'desc'));
    const unsub = onSnapshot(q, (snap) => {
      setBins(snap.docs.map((d) => d.data() as BinDoc));
    });
    return () => unsub();
  }, [user, isSuperAdmin, myOrgId]);

  // Telemetry with filters
  useEffect(() => {
    if (!user) return;
    setLoading(true);
    const base = collection(db, 'telemetry');

    const constraints: any[] = [];
    if (!isSuperAdmin) constraints.push(where('orgId', '==', myOrgId));
    if (selectedBin !== 'all') constraints.push(where('binCode', '==', selectedBin));
    if (rangeStart) constraints.push(where('timestamp', '>=', rangeStart));
    constraints.push(orderBy('timestamp', 'desc'));

    const q = query(base, ...constraints);
    const unsub = onSnapshot(q, (snap) => {
      setTelemetry(snap.docs.map((d) => d.data() as TelemetryDoc));
      setLoading(false);
    }, (err) => {
      console.error('analytics error:', err);
      setLoading(false);
    });
    return () => unsub();
  }, [user, isSuperAdmin, myOrgId, selectedBin, rangeStart]);

  const totalItems = telemetry.length;
  const recyclableItems = telemetry.filter((t) => t.recyclable).length;
  const correctDisposals = telemetry.filter((t) => t.disposalCorrect).length;
  const recyclabilityRate = totalItems > 0 ? ((recyclableItems / totalItems) * 100).toFixed(1) : '0.0';
  const accuracyRate = totalItems > 0 ? ((correctDisposals / totalItems) * 100).toFixed(1) : '0.0';

  const wasteCategories = useMemo(() => buildWasteCategories(telemetry), [telemetry]);
  const disposalTrend = useMemo(() => buildDisposalTrend(telemetry), [telemetry]);
  const binCodes = useMemo(() => bins.map((b) => (b.binCode || '').trim().toUpperCase()).filter(Boolean), [bins]);

  const tooltipStyle = { backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' };
  const empty = (
    <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
      No data for selected range.
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl text-gray-900 mb-2">Analytics</h1>
        <p className="text-gray-600">
          Detailed waste management analytics and insights
          {loading && <span className="ml-2 text-xs text-gray-400">(loading...)</span>}
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-700 mb-2">Date Range</label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Time</option>
              <option value="daily">Today</option>
              <option value="weekly">Last 7 Days</option>
              <option value="monthly">Last 30 Days</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-2">Bin</label>
            <select
              value={selectedBin}
              onChange={(e) => setSelectedBin(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Bins</option>
              {binCodes.map((code) => (
                <option key={code} value={code}>{code}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-emerald-50 to-white rounded-xl shadow-sm p-6 border border-emerald-100">
          <h3 className="text-sm text-gray-600 mb-2">Recyclability Rate</h3>
          <p className="text-3xl text-emerald-600 mb-1">{recyclabilityRate}%</p>
          <p className="text-xs text-gray-500">{recyclableItems.toLocaleString()} recyclable items</p>
        </div>
        <div className="bg-gradient-to-br from-green-50 to-white rounded-xl shadow-sm p-6 border border-green-100">
          <h3 className="text-sm text-gray-600 mb-2">Accuracy Rate</h3>
          <p className="text-3xl text-green-600 mb-1">{accuracyRate}%</p>
          <p className="text-xs text-gray-500">{correctDisposals.toLocaleString()} correct disposals</p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-white rounded-xl shadow-sm p-6 border border-blue-100">
          <h3 className="text-sm text-gray-600 mb-2">Total Items Processed</h3>
          <p className="text-3xl text-blue-600 mb-1">{totalItems.toLocaleString()}</p>
          <p className="text-xs text-gray-500">
            {dateRange === 'daily' ? "Today" : dateRange === 'weekly' ? 'Last 7 days' : dateRange === 'monthly' ? 'Last 30 days' : 'All time'}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="space-y-6">
        {/* Waste Category Distribution */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-6">Waste Category Distribution</h2>
          {wasteCategories.length === 0 && !loading ? empty : (
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={wasteCategories}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="category" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Bar dataKey="recyclable" fill="#10b981" name="Recyclable" radius={[8, 8, 0, 0]} />
                <Bar dataKey="nonRecyclable" fill="#ef4444" name="Non-Recyclable" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Disposal Correctness Trend */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-6">Disposal Correctness Trend (Last 7 Days)</h2>
          {disposalTrend.every((d) => d.correct === 0 && d.incorrect === 0) && !loading ? empty : (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={disposalTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="correct"
                  stroke="#10b981"
                  strokeWidth={3}
                  dot={{ fill: '#10b981', r: 5 }}
                  name="Correct Disposal"
                />
                <Line
                  type="monotone"
                  dataKey="incorrect"
                  stroke="#ef4444"
                  strokeWidth={3}
                  dot={{ fill: '#ef4444', r: 5 }}
                  name="Incorrect Disposal"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
};
