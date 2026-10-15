import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

/** Trend of API net-sales figures. The table remains the displayed total. */
export function SalesChart({
  points,
}: {
  points: { period: string; net: number }[]
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" />
          <YAxis />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="net"
            stroke="var(--primary)"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
