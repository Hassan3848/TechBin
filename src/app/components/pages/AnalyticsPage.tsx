import React, { useState } from 'react';
import { BarChart, Bar, LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

export const AnalyticsPage: React.FC = () => {
  const [dateRange, setDateRange] = useState('daily');
  const [selectedBin, setSelectedBin] = useState('all');

  const wasteCategories = [
    { category: 'Plastic', recyclable: 245, nonRecyclable: 87 },
    { category: 'Paper', recyclable: 189, nonRecyclable: 34 },
    { category: 'Glass', recyclable: 156, nonRecyclable: 12 },
    { category: 'Metal', recyclable: 97, nonRecyclable: 23 },
    { category: 'Organic', recyclable: 0, nonRecyclable: 198 },
    { category: 'Other', recyclable: 0, nonRecyclable: 59 },
  ];

  const disposalTrend = [
    { date: 'Mon', correct: 234, incorrect: 18 },
    { date: 'Tue', correct: 267, incorrect: 22 },
    { date: 'Wed', correct: 298, incorrect: 15 },
    { date: 'Thu', correct: 312, incorrect: 19 },
    { date: 'Fri', correct: 289, incorrect: 24 },
    { date: 'Sat', correct: 156, incorrect: 12 },
    { date: 'Sun', correct: 142, incorrect: 10 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl text-gray-900 mb-2">Analytics</h1>
          <p className="text-gray-600">Detailed waste management analytics and insights</p>
        </div>
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
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-2">Bin ID</label>
            <select
              value={selectedBin}
              onChange={(e) => setSelectedBin(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Bins</option>
              <option value="bin-001">BIN-001</option>
              <option value="bin-002">BIN-002</option>
              <option value="bin-003">BIN-003</option>
              <option value="bin-004">BIN-004</option>
              <option value="bin-005">BIN-005</option>
            </select>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="space-y-6">
        {/* Waste Category Distribution */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-6">Waste Category Distribution</h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={wasteCategories}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="category" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                }}
              />
              <Legend />
              <Bar dataKey="recyclable" fill="#10b981" name="Recyclable" radius={[8, 8, 0, 0]} />
              <Bar dataKey="nonRecyclable" fill="#ef4444" name="Non-Recyclable" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Correct vs Incorrect Disposal Over Time */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-6">Disposal Correctness Trend</h2>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={disposalTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" stroke="#9ca3af" />
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
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gradient-to-br from-emerald-50 to-white rounded-xl shadow-sm p-6 border border-emerald-100">
            <h3 className="text-sm text-gray-600 mb-2">Recyclability Rate</h3>
            <p className="text-3xl text-emerald-600 mb-1">62.4%</p>
            <p className="text-xs text-gray-500">687 recyclable items identified</p>
          </div>
          <div className="bg-gradient-to-br from-green-50 to-white rounded-xl shadow-sm p-6 border border-green-100">
            <h3 className="text-sm text-gray-600 mb-2">Accuracy Rate</h3>
            <p className="text-3xl text-green-600 mb-1">92.3%</p>
            <p className="text-xs text-gray-500">1,151 correct disposals</p>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-white rounded-xl shadow-sm p-6 border border-blue-100">
            <h3 className="text-sm text-gray-600 mb-2">Total Items Processed</h3>
            <p className="text-3xl text-blue-600 mb-1">1,247</p>
            <p className="text-xs text-gray-500">Today's total</p>
          </div>
        </div>
      </div>
    </div>
  );
};
