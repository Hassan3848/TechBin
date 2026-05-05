import React from 'react';
import { TrendingUp, TrendingDown, Recycle, Trash2, CheckCircle, XCircle } from 'lucide-react';
import { LineChart, Line, PieChart, Pie, Cell, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

export const DashboardOverview: React.FC = () => {
  // Mock data
  const dailyData = [
    { time: '00:00', items: 12 },
    { time: '04:00', items: 8 },
    { time: '08:00', items: 45 },
    { time: '12:00', items: 78 },
    { time: '16:00', items: 62 },
    { time: '20:00', items: 34 },
    { time: '23:59', items: 18 },
  ];

  const recyclabilityData = [
    { name: 'Recyclable', value: 687, color: '#10b981' },
    { name: 'Non-Recyclable', value: 413, color: '#ef4444' },
  ];

  const stats = [
    {
      title: 'Total Waste Items Today',
      value: '1,247',
      change: '+12.5%',
      isPositive: true,
      icon: Trash2,
      bgColor: 'bg-blue-50',
      iconColor: 'text-blue-600',
    },
    {
      title: 'Recyclable Items',
      value: '687',
      percentage: '55%',
      isPositive: true,
      icon: Recycle,
      bgColor: 'bg-emerald-50',
      iconColor: 'text-emerald-600',
    },
    {
      title: 'Correct Disposal Rate',
      value: '92.3%',
      change: '+3.2%',
      isPositive: true,
      icon: CheckCircle,
      bgColor: 'bg-green-50',
      iconColor: 'text-green-600',
    },
    {
      title: 'Active Bins',
      value: '24/25',
      percentage: '96%',
      isPositive: true,
      icon: XCircle,
      bgColor: 'bg-gray-50',
      iconColor: 'text-gray-600',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl text-gray-900 mb-2">Dashboard Overview</h1>
        <p className="text-gray-600">Real-time monitoring and analytics summary</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <div key={index} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <div className="flex items-start justify-between mb-4">
              <div className={`w-12 h-12 rounded-lg ${stat.bgColor} flex items-center justify-center`}>
                <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
              </div>
              {stat.change && (
                <div
                  className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
                    stat.isPositive ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                  }`}
                >
                  {stat.isPositive ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : (
                    <TrendingDown className="w-3 h-3" />
                  )}
                  {stat.change}
                </div>
              )}
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
          <h2 className="text-lg text-gray-900 mb-4">Daily Disposal Trend</h2>
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
        </div>

        {/* Recyclability Distribution */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4">Recyclability Distribution</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={recyclabilityData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={100}
                fill="#8884d8"
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
              <span className="text-sm text-gray-600">Recyclable: 687</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded-full" />
              <span className="text-sm text-gray-600">Non-Recyclable: 413</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
