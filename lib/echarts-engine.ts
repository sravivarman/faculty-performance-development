import * as core from "echarts/core";
import {BarChart,LineChart} from "echarts/charts";
import {GridComponent,TooltipComponent,LegendComponent,AriaComponent} from "echarts/components";
import {SVGRenderer} from "echarts/renderers";
core.use([BarChart,LineChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,SVGRenderer]);
export {core};
