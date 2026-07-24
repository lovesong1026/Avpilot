import { BarChart, LineChart, PieChart } from "echarts/charts";
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

use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer]);

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
  const tokenTrend: EChartsCoreOption = {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["输入 Token", "输出 Token"] },
    grid: { left: 52, right: 18, top: 24, bottom: 48 },
    xAxis: {
      type: "category",
      data: data.observability.token_trend.map((item) => item.date.slice(5)),
      axisLabel: { color: "#77857d", fontSize: 10 },
    },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#edf1ed" } } },
    series: [
      {
        name: "输入 Token",
        type: "line",
        smooth: true,
        data: data.observability.token_trend.map((item) => item.input_tokens),
        lineStyle: { color: "#315f4d", width: 3 },
        itemStyle: { color: "#315f4d" },
      },
      {
        name: "输出 Token",
        type: "line",
        smooth: true,
        data: data.observability.token_trend.map((item) => item.output_tokens),
        lineStyle: { color: "#b47b55", width: 3 },
        itemStyle: { color: "#b47b55" },
      },
    ],
  };
  const tools: EChartsCoreOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 108, right: 24, top: 20, bottom: 24 },
    xAxis: { type: "value", minInterval: 1 },
    yAxis: {
      type: "category",
      data: data.observability.tool_distribution.map((item) => item.name),
      axisLabel: { color: "#66756d", width: 96, overflow: "truncate" },
    },
    series: [{
      type: "bar",
      data: data.observability.tool_distribution.map((item) => item.value),
      itemStyle: { color: "#52796f", borderRadius: [0, 6, 6, 0] },
    }],
  };
  return (
    <section className="dashboard-charts">
      <article><h3>近 14 天记忆轨迹</h3><Chart option={line} label="近14天记忆新增趋势折线图" /></article>
      <article><h3>{data.tag_distribution.length ? "知识标签分布" : "记忆社区分布"}</h3><Chart option={pie} label="内容分类分布环形图" /></article>
      <article><h3>近 14 天 Token</h3><Chart option={tokenTrend} label="近14天输入与输出Token趋势图" /></article>
      <article><h3>Agent 工具调用</h3><Chart option={tools} label="Agent工具调用次数条形图" /></article>
    </section>
  );
}
