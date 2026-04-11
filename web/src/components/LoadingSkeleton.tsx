export function DishCardSkeleton() {
  return (
    <div className="bg-paper border border-border-warm p-6">
      <div className="skeleton h-6 w-3/4 mb-3" />
      <div className="skeleton h-5 w-1/4 mb-3" />
      <div className="skeleton h-3 w-1/2 mb-4" />
      <div className="skeleton h-3 w-full mb-2" />
      <div className="skeleton h-3 w-2/3 mb-4" />
      <div className="flex gap-2">
        <div className="skeleton h-5 w-16 rounded-full" />
        <div className="skeleton h-5 w-12 rounded-full" />
      </div>
    </div>
  );
}

export function DishGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <DishCardSkeleton key={i} />
      ))}
    </div>
  );
}
