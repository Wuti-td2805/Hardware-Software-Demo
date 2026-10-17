import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json
from datetime import datetime, timezone
from processing import fit_model, estimate
from storage import load, save

from pathlib import Path
import base64

st.set_page_config(page_title="Hardware Software Demo", page_icon="🧪", layout="wide")
image = base64.b64encode((Path(__file__).parent / "assets" / "hero.svg").read_bytes()).decode()
st.html("""<style>
.block-container {max-width:1440px; padding:1rem 2rem 2rem;}
[data-testid="stVerticalBlock"] {gap:0.65rem;}
[data-testid="stHeadingWithActionElements"] h2 {padding-top:0.4rem;padding-bottom:0.35rem;}
[data-testid="stDivider"] {margin:0.25rem 0;}
@media(max-width:640px){.block-container {padding:0.75rem 1rem 1.5rem;}}
#MainMenu {display:none;}
.hero {background:#eaf3ef; border-radius:22px; overflow:hidden; position:relative; min-height:420px; padding:48px 36px; margin-bottom:10px;}
.hero-art {position:absolute;right:-3%;top:0;width:64%;height:100%;object-fit:contain;pointer-events:none;border-radius:12px;}
.hero-reference {position:absolute;right:3%;bottom:24px;width:51%;font-size:.73rem;color:#52665e;text-align:center;}
.hero-copy {position:relative;max-width:43%;color:#173e35;}
.hero h1 {font-size:clamp(2rem,4vw,3.3rem);line-height:1.08;font-weight:600;margin:15px 0;}
.hero p {font-size:1.05rem;line-height:1.6;}
.eyebrow {font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;}
.hero a {display:inline-block;color:#173e35;margin-top:12px;font-weight:600;}
@media(max-width:640px){.hero {padding:30px 24px;min-height:0;}.hero-copy {max-width:100%;}.hero-art {position:relative;right:auto;top:auto;opacity:1;width:100%;height:auto;margin-bottom:24px;}.hero-reference {position:relative;right:auto;bottom:auto;width:100%;margin-top:20px;}}
</style>""")
st.html(f"""<section class="hero" aria-label="Hardware software introduction">
<img class="hero-art" src="data:image/svg+xml;base64,{image}" alt="Decorative sensor response curves and data points; not experimental data." />
<div class="hero-copy"><span class="eyebrow">iGEM · Hardware</span>
<h1>Hardware Software Demo</h1><p>Turn sensor readings into a calibration curve and interpretable sample results.</p>
<a href="#workspace">Explore the tools ↓</a></div></section>""")
a, b = st.columns(2)
with a:
    st.markdown("**What the result means**")
    st.write("Relative highlighter-ink concentration, expressed as % of the original stock. The stock is 100%; solvent alone is 0%.")
with b:
    st.markdown("**What this demo tests**")
    st.write("A fluorescent substitute for prototype testing. It does not measure lactate, pyruvate, or absolute dye concentration such as mg/mL.")
with st.expander("Before you begin"):
    st.markdown("""1. **Calibrate first:** enter readings for known ink dilutions, including solvent with no ink (0%).
2. **Measure unknowns the same way:** use the same original ink, light, and sensor. Keep the sample volume, tube position, and distance from the light and sensor unchanged.
3. **Keep your Arduino settings unchanged:** use the same sensor reading limit for standards and unknowns.
4. **Enter readings manually:** this demo does not read from USB. Download your results to keep a copy; records stay only in your current session and can disappear when you refresh or close the page. Other visitors have separate records.

The app draws a best-fit straight line through your readings; points do not need to fall exactly on it. Fit warnings flag scatter or reversals without preventing the graph. A fitted line alone does not establish accuracy. Readings outside the calibrated range receive no estimate. To check accuracy, measure another known dilution that was not used to build the curve.""")
st.html('<div id="workspace" style="scroll-margin-top:70px"></div>')
st.divider()

def help_label(label, explanation):
    text, icon = st.columns([12, 1])
    text.markdown(f"**{label}**")
    with icon:
        with st.popover("ⓘ", help=f"About {label}"):
            st.write(explanation)

try:
    db = load()
except Exception as e:
    st.error(f"Session records could not be loaded: {e}")
    st.stop()
model = db['model']
mode = st.radio("Workspace", ["Calibration", "Sample measurement"], horizontal=True, label_visibility="collapsed")
if model:
    st.caption(f"Active calibration: {model['stock']}")
else:
    st.html('<div role="status" style="background:#fff3f2;color:#9b4545;border-left:3px solid #e7aaa5;padding:10px 14px;border-radius:5px;font-size:0.9rem;">No calibration yet — start with Calibration.</div>')

if mode == "Calibration":
    st.header("Standard calibration")
    help_label("Calibration name", "Give this calibration a simple name, such as ‘Yellow ink test 1’, so you can recognize it later. The name does not affect the calculation.")
    stock = st.text_input("Calibration name", placeholder="Yellow ink test 1", label_visibility="collapsed")
    help_label("Sensor reading limit", "ADC means the number your Arduino reports from the sensor. Resolution determines the range of possible numbers. The reading limit is 1023 for 10-bit, 4095 for 12-bit, or 16383 for 14-bit. Match your sketch’s ADC resolution, not the largest reading you observed. The earlier photoresistor test uses 10-bit (1023).")
    adc_max = st.selectbox("Sensor reading limit", [1023, 4095, 16383], label_visibility="collapsed")
    help_label("Standard readings", "Stock (%) is the amount of original ink stock in the final mixture: 20% means 20 parts stock diluted to 100 parts total. Include a 0% solvent blank. Enter an ADC reading or average for each level; repeat a level on additional rows for replicates.")
    table = st.data_editor(pd.DataFrame({"Stock (%)": [0.,20.,40.,60.,80.,100.], "ADC": [None]*6}),
                           num_rows="dynamic", hide_index=True, key="standards", width="stretch",
                           column_config={"Stock (%)": st.column_config.NumberColumn(min_value=0,max_value=100),
                                          "ADC": st.column_config.NumberColumn(min_value=0,max_value=16383)})
    if st.button("Fit and save calibration", type="primary"):
        try:
            if not stock.strip():
                raise ValueError("Enter a calibration name.")
            candidate = fit_model(table.to_numpy(), adc_max, stock.strip())
            db['model'] = candidate
            db['models'].append(candidate)
            save(db)
            st.success("Calibration saved.")
            model = candidate
        except (ValueError, TypeError) as e:
            st.error(str(e))
    if model:
        st.subheader("Saved calibration curve")
        for message in model.get("warnings", []):
            st.warning(message)
        standards = pd.DataFrame(model['standards'], columns=['Stock (%)','ADC'])
        xx = np.linspace(model['percent_min'], model['percent_max'], 100)
        curve = pd.DataFrame({'Stock (%)':xx, 'ADC':model['slope']*xx+model['intercept']})
        points = alt.Chart(standards).mark_circle(size=85,color='#16796b').encode(x='Stock (%):Q',y='ADC:Q',tooltip=['Stock (%)','ADC'])
        line = alt.Chart(curve).mark_line(color='#244e48').encode(x='Stock (%):Q',y='ADC:Q')
        st.altair_chart(points+line,width="stretch")
        st.code(f"ADC = {model['slope']:.6g} × ink percentage + ({model['intercept']:.6g})\nInk concentration (% of original stock) = (ADC − ({model['intercept']:.6g})) / ({model['slope']:.6g})")
        st.write(f"R² = {model['r2']:.4f} · Usable ADC interval: {model['signal_min']:.2f}–{model['signal_max']:.2f}")
        with st.popover("ⓘ Reading the graph"):
            st.write("Points show your standards; the line is the fitted model. Ink percentage means concentration relative to your original stock: 100% is undiluted stock, and 0% is solvent only—not a percentage of pure dye. R² describes agreement with the line, not predictive accuracy. Only ADC readings within the displayed interval receive estimates.")
        st.download_button("Download calibration model (.json)", data=json.dumps(model, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8"), file_name="ink_calibration.json", mime="application/octet-stream", on_click="ignore", key="download_calibration")
        with st.expander("Download not starting?"):
            st.caption("Open this app in Chrome or Safari and try again. Alternatively, copy the model below into a file named ink_calibration.json.")
            st.code(json.dumps(model, indent=2, ensure_ascii=False), language="json")
else:
    st.header("Unknown sample measurement")
    st.caption("Record a sample and estimate its relative ink concentration.")
    help_label("Sample details", "Give the sample a name, then enter its Arduino ADC reading or average. Confirm that the ink stock and setup match the active calibration. Missing calibration or out-of-range readings are saved without an estimate.")
    with st.form("sample"):
        sample_id = st.text_input("Sample ID")
        adc = st.number_input("Sensor reading (ADC)", min_value=0., max_value=float(model['adc_max'] if model else 16383), value=0., step=1.)
        same_setup = st.checkbox("Same ink stock and setup as calibration")
        submit = st.form_submit_button("Record and estimate", type="primary")
    if submit:
        if not sample_id.strip():
            st.error("Enter a sample ID.")
        else:
            try:
                active = model if same_setup else None
                concentration, status = estimate(active, adc)
                if model and not same_setup:
                    status = "Setup not confirmed — no estimate"
                row = dict(timestamp=datetime.now(timezone.utc).isoformat(), sample_id=sample_id.strip(), adc=adc,
                           relative_ink_percent=concentration, status=status,
                           calibration_id=active['id'] if active else None,
                           stock_setup=active['stock'] if active else None)
                db['samples'].append(row)
                save(db)
                if concentration is None:
                    st.warning("ADC recorded. " + status)
                else:
                    st.metric("Exploratory relative ink estimate", f"{concentration:.2f}% of stock")
                    for message in active.get("warnings", []):
                        st.warning(message)
            except ValueError as e:
                st.error(str(e))
    st.subheader("Recorded measurements")
    if db['samples']:
        records = pd.DataFrame(db['samples'])
        st.dataframe(records,hide_index=True,width="stretch")
        valid = records.dropna(subset=['relative_ink_percent'])
        if not valid.empty:
            st.altair_chart(alt.Chart(valid).mark_circle(size=90).encode(x='sample_id:N',y=alt.Y('relative_ink_percent:Q',title='Relative ink (% stock)'),color='stock_setup:N',tooltip=['sample_id','adc','relative_ink_percent','timestamp']),width="stretch")
        st.download_button("Download measurements CSV", records.to_csv(index=False).encode("utf-8-sig"), "ink_measurements.csv", "text/csv", on_click="ignore")
    else:
        st.caption("No measurements recorded yet.")
st.divider()
st.download_button("Back up all records", json.dumps(db,indent=2).encode("utf-8"), "ink_lab_backup.json", "application/octet-stream", on_click="ignore")
