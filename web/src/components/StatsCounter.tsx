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
    fetch('/stats')
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  if (!stats || stats.total_searches < 20) return null;

  return (
    <div
      className="font-serif italic text-center text-sm md:text-base text-sand py-4 mb-6"
      data-testid="stats-text"
    >
      {stats.total_searches.toLocaleString()} dishes served to{' '}
      {stats.total_visitors.toLocaleString()} hungry{' '}
      {stats.total_visitors === 1 ? 'Calgarian' : 'Calgarians'}
      {stats.weekly_visitors > 0 && (
        <span className="text-terracotta not-italic font-sans font-semibold">
          {' · '}
          {stats.weekly_visitors} this week
        </span>
      )}
    </div>
  );
}
