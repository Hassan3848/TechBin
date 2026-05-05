import React, { useState } from 'react';
import { CircleAlert, CheckCircle, Clock, Camera, Radio, Wifi } from 'lucide-react';

interface Fault {
  id: string;
  binId: string;
  component: string;
  severity: 'Critical' | 'Warning' | 'Normal';
  timestamp: string;
  description: string;
  status: 'Resolved' | 'Unresolved';
}

export const FaultDetectionPage: React.FC = () => {
  const [filter, setFilter] = useState<'all' | 'Critical' | 'Warning' | 'Resolved'>('all');

  const faults: Fault[] = [
    {
      id: 'F001',
      binId: 'BIN-003',
      component: 'Camera',
      severity: 'Critical',
      timestamp: '2025-12-26 14:23:45',
      description: 'Camera module not responding, unable to capture images',
      status: 'Unresolved',
    },
    {
      id: 'F002',
      binId: 'BIN-007',
      component: 'Network',
      severity: 'Warning',
      timestamp: '2025-12-26 13:15:22',
      description: 'Intermittent network connectivity, packet loss detected',
      status: 'Unresolved',
    },
    {
      id: 'F003',
      binId: 'BIN-001',
      component: 'IR Sensor',
      severity: 'Warning',
      timestamp: '2025-12-26 12:45:10',
      description: 'IR sensor readings inconsistent, possible calibration needed',
      status: 'Unresolved',
    },
    {
      id: 'F004',
      binId: 'BIN-012',
      component: 'Camera',
      severity: 'Normal',
      timestamp: '2025-12-26 11:30:05',
      description: 'Camera module recovered after reboot',
      status: 'Resolved',
    },
    {
      id: 'F005',
      binId: 'BIN-005',
      component: 'Ultrasonic Sensor',
      severity: 'Critical',
      timestamp: '2025-12-26 10:22:18',
      description: 'Ultrasonic sensor failed, bin capacity cannot be determined',
      status: 'Unresolved',
    },
    {
      id: 'F006',
      binId: 'BIN-009',
      component: 'Metal Sensor',
      severity: 'Normal',
      timestamp: '2025-12-26 09:15:33',
      description: 'Metal sensor calibration completed successfully',
      status: 'Resolved',
    },
  ];

  const filteredFaults = faults.filter((fault) => {
    if (filter === 'all') return true;
    if (filter === 'Resolved') return fault.status === 'Resolved';
    return fault.severity === filter;
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'Critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'Warning':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Normal':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'Critical':
        return <CircleAlert className="w-5 h-5 text-red-600" />;
      case 'Warning':
        return <CircleAlert className="w-5 h-5 text-yellow-600" />;
      case 'Normal':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      default:
        return null;
    }
  };

  const getComponentIcon = (component: string) => {
    switch (component.toLowerCase()) {
      case 'camera':
        return <Camera className="w-5 h-5" />;
      case 'network':
        return <Wifi className="w-5 h-5" />;
      default:
        return <Radio className="w-5 h-5" />;
    }
  };

  const criticalCount = faults.filter((f) => f.severity === 'Critical' && f.status === 'Unresolved').length;
  const warningCount = faults.filter((f) => f.severity === 'Warning' && f.status === 'Unresolved').length;
  const resolvedCount = faults.filter((f) => f.status === 'Resolved').length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl text-gray-900 mb-2">Fault Detection</h1>
        <p className="text-gray-600">System health monitoring and fault management</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-red-50 to-white rounded-xl shadow-sm p-6 border border-red-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <CircleAlert className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <p className="text-3xl text-red-600">{criticalCount}</p>
              <p className="text-sm text-gray-600">Critical Faults</p>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-yellow-50 to-white rounded-xl shadow-sm p-6 border border-yellow-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <CircleAlert className="w-6 h-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-3xl text-yellow-600">{warningCount}</p>
              <p className="text-sm text-gray-600">Warnings</p>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-white rounded-xl shadow-sm p-6 border border-green-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-3xl text-green-600">{resolvedCount}</p>
              <p className="text-sm text-gray-600">Resolved Today</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            filter === 'all'
              ? 'bg-emerald-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          All Faults
        </button>
        <button
          onClick={() => setFilter('Critical')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            filter === 'Critical'
              ? 'bg-red-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          Critical
        </button>
        <button
          onClick={() => setFilter('Warning')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            filter === 'Warning'
              ? 'bg-yellow-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          Warnings
        </button>
        <button
          onClick={() => setFilter('Resolved')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            filter === 'Resolved'
              ? 'bg-green-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          Resolved
        </button>
      </div>

      {/* Fault List */}
      <div className="space-y-4">
        {filteredFaults.map((fault) => (
          <div
            key={fault.id}
            className={`bg-white rounded-xl shadow-sm p-6 border ${getSeverityColor(
              fault.severity
            )}`}
          >
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div className="flex items-start gap-4 flex-1">
                <div className="flex-shrink-0">{getSeverityIcon(fault.severity)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-xs">
                      {fault.id}
                    </span>
                    <span className="px-3 py-1 bg-emerald-50 text-emerald-800 rounded-full text-xs">
                      {fault.binId}
                    </span>
                    <div className="flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-800 rounded-full text-xs">
                      {getComponentIcon(fault.component)}
                      <span>{fault.component}</span>
                    </div>
                  </div>
                  <p className="text-gray-900 mb-2">{fault.description}</p>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <Clock className="w-4 h-4" />
                    <span>{fault.timestamp}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`px-4 py-2 rounded-lg text-sm ${
                    fault.status === 'Resolved'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {fault.status}
                </span>
                {fault.status === 'Unresolved' && (
                  <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors text-sm">
                    Resolve
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
