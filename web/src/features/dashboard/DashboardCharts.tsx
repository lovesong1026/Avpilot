import { LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

import type { DashboardData } from "../../entities/navigation";

use([LineChart, PieChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer]);

function Chart({ option, label }: { option: EChartsCoreOption; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = init(ref.current);
    chart.setOption(option);
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(ref.current);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  }, [option]);
  return <div className="dashboard-chart" ref={ref} role="img" aria-label={label} />;
}

export function DashboardCharts({ data }: { data: DashboardData }) {
  const line: EChartsCoreOption = {
    tooltip: { trigger: "axis" },
    grid: { left: 38, right: 18, top: 42, bottom: 28 },
    xAxis: {
      type: "category",
      data: data.memory_trend.map((item) => item.date.slice(5)),
      axisLine: { lineStyle: { color: "#c8d5cc" } },
      axisLabel: { color: "#77857d", fontSize: 10 },
    },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#edf1ed" } } },
    series: [{
      name: "新增记忆",
      type: "line",
      smooth: true,
      symbolSize: 7,
      data: data.memory_trend.map((item) => item.value),
      lineStyle: { color: "#3f735b", width: 3 },
      itemStyle: { color: "#3f735b" },
      areaStyle: { color: "rgba(83, 135, 106, .16)" },
    }],
  };
  const distribution = data.tag_distribution.length
    ? data.tag_distribution
    : data.community_distribution;
  const pie: EChartsCoreOption = {
    tooltip: { trigger: "item" },
    legend: { type: "scroll", bottom: 0, textStyle: { color: "#66756d", fontSize: 10 } },
    color: ["#315f4d", "#52796f", "#7a927d", "#98ad91", "#b3c4a9", "#7a6c5d"],
    series: [{
      name: data.tag_distribution.length ? "标签内容" : "记忆社区",
      type: "pie",
      radius: ["43%", "68%"],
      center: ["50%", "44%"],
      label: { color: "#53645b", fontSize: 10 },
      data: distribution,
    }],
  };
  return (
    <section className="dashboard-charts">
      <article><h3>近 14 天记忆轨迹</h3><Chart option={line} label="近14天记忆新增趋势折线图" /></article>
      <article><h3>{data.tag_distribution.length ? "知识标签分布" : "记忆社区分布"}</h3><Chart option={pie} label="内容分类分布环形图" /></article>
    </section>
  );
}
