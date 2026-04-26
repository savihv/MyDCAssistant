import React from "react";

export interface Props {
  templateId: string;
  suCount: number;
  nodesPerSu: number;
  gpusPerNode: number;
  leafSwitchesPerSu: number;
  spineswitches: number;
}

const NODE_COLOR = "#22c55e";
const LEAF_COLOR = "#3b82f6";
const SPINE_COLOR = "#f59e0b";
const LINE_COLOR = "#374151";

export default function TopologyPreview({
  templateId,
  suCount,
  nodesPerSu,
  gpusPerNode,
  leafSwitchesPerSu,
  spineswitches,
}: Props) {
  const hasSpine = spineswitches > 0;

  // Cap for visual sanity
  const visibleSUs = Math.min(suCount, 4);
  const visibleNodes = Math.min(nodesPerSu, 4);
  const visibleLeafs = Math.min(leafSwitchesPerSu, 4);
  const visibleSpines = Math.min(spineswitches, 4);

  const suWidth = 160;
  const suGap = 24;
  const totalWidth = Math.max(600, visibleSUs * (suWidth + suGap) + suGap + (hasSpine ? 120 : 0));
  const svgHeight = hasSpine ? 320 : 240;

  // Y positions
  const spineY = 40;
  const leafY = hasSpine ? 120 : 60;
  const nodeY = hasSpine ? 220 : 160;

  const centerX = totalWidth / 2;

  return (
    <div className="w-full overflow-x-auto bg-gray-900 rounded-lg border border-gray-700 p-4">
      <div className="text-xs text-gray-400 mb-2 flex items-center gap-4">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: SPINE_COLOR }} />
          Spine Switch
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: LEAF_COLOR }} />
          Leaf Switch
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: NODE_COLOR }} />
          Compute Node ({gpusPerNode} GPUs)
        </span>
      </div>
      <svg
        width={totalWidth}
        height={svgHeight}
        viewBox={`0 0 ${totalWidth} ${svgHeight}`}
        className="block"
      >
        {/* Spine row */}
        {hasSpine &&
          Array.from({ length: visibleSpines }).map((_, si) => {
            const spineSpacing = totalWidth / (visibleSpines + 1);
            const sx = spineSpacing * (si + 1);
            return (
              <g key={`spine-${si}`}>
                <rect
                  x={sx - 28}
                  y={spineY - 14}
                  width={56}
                  height={28}
                  rx={4}
                  fill={SPINE_COLOR}
                  opacity={0.9}
                />
                <text x={sx} y={spineY + 5} textAnchor="middle" fontSize={9} fill="#1f2937" fontWeight="bold">
                  Spine {si + 1}
                </text>
              </g>
            );
          })}

        {/* SU columns */}
        {Array.from({ length: visibleSUs }).map((_, sui) => {
          const suStart = suGap + sui * (suWidth + suGap);
          const suCenter = suStart + suWidth / 2;

          return (
            <g key={`su-${sui}`}>
              {/* SU label */}
              <text
                x={suCenter}
                y={leafY - 22}
                textAnchor="middle"
                fontSize={10}
                fill="#9ca3af"
              >
                SU {sui + 1}
              </text>

              {/* Leaf switches in this SU */}
              {Array.from({ length: visibleLeafs }).map((_, li) => {
                const leafSpacing = suWidth / (visibleLeafs + 1);
                const lx = suStart + leafSpacing * (li + 1);

                return (
                  <g key={`leaf-${sui}-${li}`}>
                    {/* Line from spine to leaf */}
                    {hasSpine &&
                      Array.from({ length: visibleSpines }).map((_, si) => {
                        const spineSpacing = totalWidth / (visibleSpines + 1);
                        const sx = spineSpacing * (si + 1);
                        return (
                          <line
                            key={`sl-${sui}-${li}-${si}`}
                            x1={sx}
                            y1={spineY + 14}
                            x2={lx}
                            y2={leafY - 12}
                            stroke={LINE_COLOR}
                            strokeWidth={1}
                            opacity={0.5}
                          />
                        );
                      })}

                    {/* Leaf box */}
                    <rect
                      x={lx - 22}
                      y={leafY - 12}
                      width={44}
                      height={24}
                      rx={3}
                      fill={LEAF_COLOR}
                      opacity={0.9}
                    />
                    <text x={lx} y={leafY + 3} textAnchor="middle" fontSize={8} fill="#fff">
                      Leaf {li + 1}
                    </text>

                    {/* Lines from leaf to nodes */}
                    {Array.from({ length: visibleNodes }).map((_, ni) => {
                      const nodeSpacing = suWidth / (visibleNodes + 1);
                      const nx = suStart + nodeSpacing * (ni + 1);
                      return (
                        <line
                          key={`ln-${sui}-${li}-${ni}`}
                          x1={lx}
                          y1={leafY + 12}
                          x2={nx}
                          y2={nodeY - 12}
                          stroke={LINE_COLOR}
                          strokeWidth={1}
                          opacity={0.4}
                        />
                      );
                    })}
                  </g>
                );
              })}

              {/* Compute nodes */}
              {Array.from({ length: visibleNodes }).map((_, ni) => {
                const nodeSpacing = suWidth / (visibleNodes + 1);
                const nx = suStart + nodeSpacing * (ni + 1);
                return (
                  <g key={`node-${sui}-${ni}`}>
                    <rect
                      x={nx - 22}
                      y={nodeY - 12}
                      width={44}
                      height={26}
                      rx={3}
                      fill={NODE_COLOR}
                      opacity={0.85}
                    />
                    <text x={nx} y={nodeY + 1} textAnchor="middle" fontSize={7} fill="#fff">
                      Node {ni + 1}
                    </text>
                    <text x={nx} y={nodeY + 11} textAnchor="middle" fontSize={7} fill="#dcfce7">
                      {gpusPerNode} GPUs
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}

        {/* Truncation hints */}
        {suCount > visibleSUs && (
          <text
            x={totalWidth - 8}
            y={leafY + 4}
            textAnchor="end"
            fontSize={11}
            fill="#6b7280"
          >
            +{suCount - visibleSUs} more SUs
          </text>
        )}
      </svg>
      <div className="mt-2 text-xs text-gray-500 text-center">
        {suCount > visibleSUs || nodesPerSu > visibleNodes
          ? `Showing simplified view — actual deployment has ${suCount} SUs × ${nodesPerSu} nodes × ${gpusPerNode} GPUs`
          : `${suCount} SU${suCount > 1 ? "s" : ""} · ${suCount * nodesPerSu} nodes · ${suCount * nodesPerSu * gpusPerNode} total GPUs`}
      </div>
    </div>
  );
}
