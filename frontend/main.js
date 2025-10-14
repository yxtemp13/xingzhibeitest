const hostsContainer = document.getElementById("hosts");
const jobsContainer = document.getElementById("jobs");
const profilesContainer = document.getElementById("profiles");
const cpuChartElement = document.getElementById("cpu-chart");
const jobForm = document.getElementById("job-form");
const chart = echarts.init(cpuChartElement);

function renderHosts(hosts) {
  hostsContainer.innerHTML = hosts
    .map(
      (host) => `
      <article>
        <h3>${host.name}</h3>
        <p>Exporter: ${host.address}</p>
        <p>${Object.entries(host.labels)
          .map(([key, value]) => `${key}: ${value}`)
          .join(" · ")}</p>
      </article>
    `
    )
    .join("");
}

function renderCpuChart(data) {
  const times = data[0]?.values.map((item) => new Date(item[0] * 1000)) ?? [];
  const series = data.map((item) => ({
    name: `${item.metric.instance} (${item.metric.mode})`,
    type: "line",
    showSymbol: false,
    smooth: true,
    data: item.values.map((entry) => [entry[0] * 1000, Number(entry[1])]),
  }));
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    xAxis: { type: "time" },
    yAxis: { type: "value", name: "CPU 秒" },
    series,
  });
}

function renderJobs(jobs) {
  if (jobs.length === 0) {
    jobsContainer.textContent = "暂无任务";
    return;
  }
  jobsContainer.innerHTML = jobs
    .map(
      (job) =>
        `${job.job_id} | ${job.job_type} @ ${job.target} | 状态: ${job.status} | 模式: ${job.mode}`
    )
    .join("\n");
}

function renderProfiles(profiles) {
  profilesContainer.innerHTML = profiles
    .map(
      (profile) => `
      <article>
        <h3>${profile.title}</h3>
        <p>服务：${profile.service}</p>
        <p>采样率：${profile.sample_rate_hz.toFixed(1)} Hz</p>
        <p>采集时间：${new Date(profile.created_at).toLocaleString()}</p>
      </article>
    `
    )
    .join("");
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`);
  }
  return response.json();
}

async function refreshHosts() {
  const hosts = await fetchJson("/api/hosts");
  renderHosts(hosts);
}

async function refreshCpu() {
  const end = new Date();
  const start = new Date(end.getTime() - 15 * 60 * 1000);
  const params = new URLSearchParams({
    expr: 'node_cpu_seconds_total{mode="user"}',
    start: start.toISOString(),
    end: end.toISOString(),
    step: "60",
  });
  const result = await fetchJson(`/api/query_range?${params.toString()}`);
  renderCpuChart(result.data.result ?? []);
}

async function refreshJobs() {
  const result = await fetchJson("/api/diagnose/jobs");
  renderJobs(result.jobs);
}

async function refreshProfiles() {
  const result = await fetchJson("/api/profiles");
  renderProfiles(result.profiles);
}

jobForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(jobForm);
  const payload = {
    job_type: formData.get("job_type"),
    target: formData.get("target"),
    duration: Number(formData.get("duration")),
  };
  await fetchJson("/api/diagnose/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  jobForm.reset();
  await refreshJobs();
});

async function bootstrap() {
  await Promise.all([refreshHosts(), refreshCpu(), refreshJobs(), refreshProfiles()]);
  setInterval(refreshCpu, 60000);
  setInterval(refreshJobs, 5000);
}

bootstrap().catch((error) => {
  console.error(error);
  jobsContainer.textContent = error.message;
});
