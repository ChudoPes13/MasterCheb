class MasterChebAudioProcessor extends AudioWorkletProcessor {
 process(inputs){const c=inputs[0]?.[0];if(!c)return true;const samples=new Float32Array(c);let sum=0;for(const v of samples)sum+=v*v;this.port.postMessage({samples,rms:Math.sqrt(sum/samples.length)},[samples.buffer]);return true}
}
registerProcessor("mastercheb-audio-processor",MasterChebAudioProcessor);
