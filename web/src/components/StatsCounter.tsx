import { useEffect, useState } from 'react';

interface Stats {
  total_visitors: number;
  total_searches: number;
  total_chats: number;
  weekly_visitors: number;
}

export default function StatsCounter() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    fetch('/stats').then(r => r.json()).then(setStats).catch(() => {});
  }, []);

  if (!stats || stats.total_visitors === 0) return null;

  return (
    <div className="text-center text-sm text-text-secondary py-4">
      {stats.total_searches.toLocaleString()} dishes served to {stats.total_visitors.toLocaleString()} hungry Calgarians
      {stats.weekly_visitors > 0 && <span className="text-accent"> · {stats.weekly_visitors} this week</span>}
    </div>
  );
}
