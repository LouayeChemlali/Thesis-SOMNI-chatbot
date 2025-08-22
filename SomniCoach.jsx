'use client';
import { useEffect, useState } from 'react';
import Image from 'next/image';

export default function SomniWakeup() {
  // variant intern vastleggen: 'eerste' of 'tweede'
  const [variant, setVariant] = useState('eerste'); // 'eerste' of 'tweede'

  // chat state
  const [messages, setMessages] = useState([]);
  const [stateId, setStateId] = useState(null);
  const [answers, setAnswers] = useState({});
  const [inputType, setInputType] = useState(null);
  const [options, setOptions] = useState(null);
  const [labels, setLabels] = useState(null);
  const [isOptional, setIsOptional] = useState(false);
  const [textValue, setTextValue] = useState('');
  const [multiSel, setMultiSel] = useState([]);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);

  // start or restart on variant change
  useEffect(() => {
    startChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variant]);

  async function startChat() {
    setMessages([]);
    setStateId(null);
    setAnswers({});
    setInputType(null);
    setOptions(null);
    setLabels(null);
    setIsOptional(false);
    setDone(false);
    setTextValue('');
    setMultiSel([]);
    setSummary(null);

    const res = await fetch('http://localhost:5000/api/somni-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant, state_id: null })
    });
    const data = await res.json();
    setMessages([{ role: 'assistant', content: data.reply }]);
    setStateId(data.next_state_id);
    setInputType(data.input_type);
    setOptions(data.options || null);
    setLabels(data.labels || null);
    setIsOptional(!!data.is_optional);
    setAnswers(data.answers || {});
    setDone(!!data.done);
  }

  async function sendUserInput(value) {
    if (busy || done) return;
    setBusy(true);

    const userMsg = value === '' ? (isOptional ? '(overgeslagen)' : '') : value;
    setMessages(prev => [
      ...prev,
      { role: 'user', content: Array.isArray(userMsg) ? userMsg.join(', ') : String(userMsg || '(overgeslagen)') }
    ]);

    try {
      const res = await fetch('http://localhost:5000/api/somni-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          variant,
          state_id: stateId,
          user_input: value,
          answers
        })
      });
      const data = await res.json();

      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      setStateId(data.next_state_id);
      setInputType(data.input_type);
      setOptions(data.options || null);
      setLabels(data.labels || null);
      setIsOptional(!!data.is_optional);
      setAnswers(data.answers || {});
      setDone(!!data.done);

      setTextValue('');
      setMultiSel([]);
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  function renderInput() {
    if (done) return null;

    const btnBlue = 'px-3 py-2 rounded-lg border border-blue-700 bg-blue-600 text-white hover:bg-blue-700 transition';
    const btnGhost = 'px-3 py-2 rounded-lg border border-black text-black bg-white hover:bg-gray-100 transition';

    if (inputType === 'ack') {
      return (
        <button onClick={() => sendUserInput('OK')} className={btnBlue}>
          Start
        </button>
      );
    }

    if (inputType === 'likert11' && Array.isArray(labels)) {
      return (
        <div className="flex flex-wrap gap-2">
          {labels.map(l => (
            <button key={l} onClick={() => sendUserInput(l)} className={btnBlue}>
              {l}
            </button>
          ))}
        </div>
      );
    }

    if (inputType === 'select' && Array.isArray(options)) {
      return (
        <div className="flex flex-wrap gap-2">
          {options.map(opt => (
            <button key={opt} onClick={() => sendUserInput(opt)} className={btnBlue}>
              {opt}
            </button>
          ))}
        </div>
      );
    }

    if (inputType === 'multiselect' && Array.isArray(options)) {
      return (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {options.map(opt => {
              const active = multiSel.includes(opt);
              return (
                <button
                  key={opt}
                  onClick={() =>
                    setMultiSel(prev => (active ? prev.filter(x => x !== opt) : [...prev, opt]))
                  }
                  className={
                    active
                      ? 'px-3 py-2 rounded-lg border border-blue-700 bg-blue-600 text-white hover:bg-blue-700 transition'
                      : 'px-3 py-2 rounded-lg border border-blue-700 bg-white text-blue-700 hover:bg-blue-600 hover:text-white transition'
                  }
                >
                  {opt}
                </button>
              );
            })}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => sendUserInput(multiSel)}
              className={btnBlue + ' disabled:opacity-50'}
              disabled={multiSel.length === 0}
            >
              Verstuur selectie
            </button>
            <button onClick={() => setMultiSel([])} className={btnGhost}>
              Reset
            </button>
          </div>
        </div>
      );
    }

    if (inputType === 'text' || inputType === 'text_optional') {
      return (
        <div className="flex w-full gap-2">
          <input
            type="text"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-black focus:outline-none"
            value={textValue}
            placeholder={isOptional ? 'Optioneel' : 'Typ je antwoord'}
            onChange={e => setTextValue(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') sendUserInput(textValue.trim());
            }}
          />
          <button
            onClick={() => sendUserInput(textValue.trim())}
            className={btnBlue + ' disabled:opacity-50'}
            disabled={!isOptional && textValue.trim() === ''}
          >
            Verstuur
          </button>
          {isOptional && (
            <button onClick={() => sendUserInput('')} className={btnGhost}>
              Overslaan
            </button>
          )}
        </div>
      );
    }

    return null;
  }

  async function getSummary() {
    const res = await fetch('http://localhost:5000/api/wakeup-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers, variant })
    });
    const data = await res.json();
    setSummary(data.summary);
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full flex flex-col overflow-hidden border">
        {/* Header */}
        <div className="bg-blue-50 px-6 py-4 flex items-center justify-between border-b">
          <div className="flex items-center gap-4">
            <Image src="/somni-avatar.png" alt="SOMNI" width={60} height={60} className="rounded-full border shadow" />
            <h1 className="text-2xl font-semibold text-gray-800">
              SOMNI Wake-up check-in
            </h1>
          </div>

          {/* Variant switcher top right */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Variant</span>
            <div className="bg-white border border-gray-300 rounded-xl p-1 flex">
              <button
                className={`px-3 py-1 text-sm rounded-lg ${
                  variant === 'eerste'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-800 hover:bg-gray-100'
                }`}
                onClick={() => setVariant('eerste')}
                aria-pressed={variant === 'eerste'}
              >
                Eerste variant
              </button>
              <button
                className={`px-3 py-1 text-sm rounded-lg ${
                  variant === 'tweede'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-800 hover:bg-gray-100'
                }`}
                onClick={() => setVariant('tweede')}
                aria-pressed={variant === 'tweede'}
              >
                Tweede variant
              </button>
            </div>
          </div>
        </div>

        {/* Chat history */}
        <div className="p-6 flex flex-col gap-4 h-[28rem] overflow-y-auto bg-gray-50">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`self-${m.role === 'user' ? 'end' : 'start'} max-w-[75%] px-4 py-2 rounded-xl shadow text-sm ${
                m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-900'
              }`}
            >
              {m.content}
            </div>
          ))}
        </div>

        {/* Input area */}
        <div className="flex flex-col gap-3 border-t px-4 py-3 bg-white">
          {!done ? (
            renderInput()
          ) : (
            <>
              <button
                onClick={getSummary}
                className="px-3 py-2 rounded-lg border border-blue-700 bg-blue-600 text-white hover:bg-blue-700 transition"
              >
                Toon korte samenvatting
              </button>
              {summary && <div className="mt-2 text-sm text-gray-800">{summary}</div>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
