import React from 'react';
import { esc } from '../services/api';

interface EntityPropertiesTableProps {
  properties: Record<string, unknown>;
  labels?: string[];
  className?: string;
}

export function formatPropertyKey(k: string): string {
  const map: Record<string, string> = {
    phone_number: 'Phone Number',
    phone_id: 'Phone ID',
    carrier: 'Carrier / Provider',
    imei: 'IMEI Hardware ID',
    imsi: 'IMSI Identifier',
    registered_owner: 'Registered Subscriber',
    owner_person_id: 'Owner Person ID',
    account_number: 'Account Number',
    account_id: 'Account ID',
    bank_name: 'Bank / Institution',
    account_type: 'Account Type',
    branch: 'Branch',
    holder_name: 'Account Holder',
    ifsc: 'IFSC Code',
    vin: 'Vehicle VIN',
    license_plate: 'Registration / Plate',
    model: 'Vehicle Model',
    color: 'Color',
    fir_number: 'FIR Number',
    fir_id: 'FIR ID',
    crime_category: 'Crime Category',
    date_filed: 'Date Filed',
    police_station: 'Police Station',
    ip_address: 'IP Address',
    isp: 'Internet Provider (ISP)',
    location_id: 'Location ID',
    address: 'Physical Address',
    cell_tower_id: 'Cell Tower ID',
    tower_code: 'Tower Code',
    handle: 'Profile Handle',
    platform: 'Platform Network',
    risk_score: 'Risk Score',
    role: 'Operational Role',
    status: 'Status'
  };
  if (map[k.toLowerCase()]) return map[k.toLowerCase()];
  return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function EntityPropertiesTable({ properties, labels, className = '' }: EntityPropertiesTableProps) {
  if (!properties) return null;

  const isPhone = (labels || []).includes('Phone') || properties.phone_number !== undefined;
  const isAccount = (labels || []).includes('BankAccount') || properties.account_number !== undefined;

  const ignoredKeys = new Set([
    'case_ids',
    'created_at',
    'updated_at',
    'communications',
    'transactions',
    'total_transactions',
    'total_amount_transferred',
    'total_calls',
    'properties',
    'labels',
    'node',
    'connections',
    'total_connections',
    'entity_id',
    'id',
    'name',
    'display_name'
  ]);

  if (isPhone) {
    ignoredKeys.add('associated_person_name');
    ignoredKeys.add('associated_person_id');
    if (properties.phone_id && properties.phone_number && String(properties.phone_id) === String(properties.phone_number)) {
      ignoredKeys.add('phone_id');
    }
  }

  if (isAccount) {
    if (properties.account_id && properties.account_number && String(properties.account_id) === String(properties.account_number)) {
      ignoredKeys.add('account_id');
    }
  }

  const entries: [string, string][] = [];
  for (const [k, v] of Object.entries(properties)) {
    if (ignoredKeys.has(k)) continue;
    if (v === null || v === undefined) continue;

    if (Array.isArray(v)) {
      if (v.length === 0) continue;
      entries.push([formatPropertyKey(k), v.join(', ')]);
      continue;
    }

    if (typeof v === 'object') {
      const s = JSON.stringify(v);
      if (s === '{}' || s === '[]') continue;
      entries.push([formatPropertyKey(k), s]);
      continue;
    }

    const valStr = String(v).trim();
    if (!valStr || valStr === '[]' || valStr === '{}' || valStr.toLowerCase() === 'unknown') continue;

    entries.push([formatPropertyKey(k), valStr]);
  }

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className={`entity-props-container ${className}`} style={{ marginBottom: '16px' }}>
      <table className="entity-props-table">
        <tbody>
          {entries.map(([label, val], idx) => (
            <tr key={idx}>
              <td className="prop-key">{label}</td>
              <td className="prop-val">{esc(val)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
