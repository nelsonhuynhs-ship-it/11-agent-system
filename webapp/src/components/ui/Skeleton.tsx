/**
 * Skeleton loading components for Nelson Freight dashboard
 */

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-border/50 ${className}`}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="card p-5">
      <Skeleton className="h-3 w-24 mb-3" />
      <Skeleton className="h-8 w-32 mb-2" />
      <Skeleton className="h-3 w-20" />
    </div>
  )
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="p-4 border-b border-border">
        <Skeleton className="h-5 w-40" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 border-b border-border last:border-0">
          <Skeleton className="h-4 w-[15%]" />
          <Skeleton className="h-4 w-[25%]" />
          <Skeleton className="h-4 w-[20%]" />
          <Skeleton className="h-4 w-[15%]" />
          <Skeleton className="h-4 w-[10%]" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="card p-5">
      <Skeleton className="h-5 w-32 mb-4" />
      <Skeleton className="h-[200px] w-full" />
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SkeletonChart />
        <SkeletonChart />
      </div>
      {/* Table */}
      <SkeletonTable />
    </div>
  )
}
