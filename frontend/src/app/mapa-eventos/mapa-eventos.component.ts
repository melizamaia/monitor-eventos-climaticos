import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import * as L from 'leaflet';
import 'leaflet.heat';
import { EventoFeature, EventosService } from '../services/eventos.service';
import { PontoTemperatura, TemperaturasService } from '../services/temperaturas.service';

// Ponto médio aproximado entre RJ e SP — só usado como fallback enquanto os
// eventos carregam ou quando a coleção vier vazia; assim que houver marcadores,
// o mapa se ajusta automaticamente a eles (ver ajustarEnquadramento).
const CENTRO_NEUTRO: L.LatLngExpression = [-23.0, -44.5];
const ZOOM_INICIAL = 7;
const ZOOM_EVENTO_UNICO = 11;

// Faixa de temperatura usada só pra normalizar a intensidade do heatmap (0 a 1),
// não é um limite físico — fixa (não calculada a partir dos dados carregados)
// pra escala de cor não mudar de execução pra execução. Cobre o range nacional
// observado nas 546 estações (INMET), do frio no Sul ao calor no Norte/Nordeste.
const TEMPERATURA_MINIMA = 10;
const TEMPERATURA_MAXIMA = 38;

// maxZoom próprio do heatLayer (não confundir com o maxZoom do tileLayer, que é
// 19): o leaflet.heat esmaga a intensidade de cada ponto por um fator
// 1 / 2^(maxZoom - zoomAtual), pensado pra heatmaps de densidade que acumulam
// muitos pontos próximos ao dar zoom in. Com 546 estações espalhadas pelo Brasil
// inteiro e visualização em zoom baixo (~7), deixar o maxZoom padrão (19) esmagava
// a intensidade de qualquer ponto a ~0.02% do valor normalizado — por isso o mapa
// nunca saía do azul/roxo, mesmo em áreas muito quentes. Fixamos próximo do zoom
// real de visualização pra intensidade normalizada valer o que ela diz que vale.
const HEATMAP_MAX_ZOOM = ZOOM_INICIAL;

// Acima deste zoom (visão de bairro/cidade), a densidade de estações é baixa
// demais (2-3 por área visível) pra o heatmap interpolar uma área contínua — ele
// "quebra" em bolhas isoladas sem sentido visual. Nesse nível já faz mais sentido
// olhar os marcadores de eventos do que tentar estimar uma área de temperatura.
const HEATMAP_ZOOM_LIMITE = 10;

// radius/blur variam com o zoom pra suavizar a transição entre a visão de país
// (poucos pontos, área grande — raio maior deixa a mancha de calor visível) e a
// visão de cidade (pontos próximos — raio menor evita que manchas se fundam numa
// coisa ilegível antes mesmo de cruzar o limite acima e o heatmap ser escondido).
const HEATMAP_ZOOM_RADIUS_MIN = 5;
const HEATMAP_RADIUS_PAIS = 40;
const HEATMAP_RADIUS_CIDADE = 18;
const HEATMAP_BLUR_PAIS = 30;
const HEATMAP_BLUR_CIDADE = 14;

// Única fonte de verdade pras cores do heatmap: usada tanto na opção `gradient`
// do L.heatLayer quanto pra montar a legenda, pra elas nunca dessincronizarem.
// Tons pastéis (não puros) pra combinar com o resto do app e não brigar com o
// mapa base por baixo — a chave é a fração de intensidade (0 a 1) de cada parada.
const GRADIENTE_HEATMAP: Record<number, string> = {
  0.2: '#3b82f6',
  0.4: '#22d3ee',
  0.6: '#a3e635',
  0.75: '#fbbf24',
  1.0: '#f87171',
};

const CORES_SEVERIDADE: Record<string, string> = {
  baixa: '#2e7d32',
  media: '#f9a825',
  média: '#f9a825',
  alta: '#c62828',
};
const COR_PADRAO = '#1565c0';

@Component({
  selector: 'app-mapa-eventos',
  standalone: true,
  templateUrl: './mapa-eventos.component.html',
  styleUrl: './mapa-eventos.component.scss',
})
export class MapaEventosComponent implements AfterViewInit, OnDestroy {
  @ViewChild('mapaEl', { static: true }) mapaEl!: ElementRef<HTMLDivElement>;

  carregando = true;
  erro: string | null = null;

  heatmapAtivo = false;
  heatmapIndisponivel = false;

  private mapa: L.Map | null = null;
  private heatLayer: L.HeatLayer | null = null;
  private legendaHeatmap: L.Control | null = null;

  constructor(
    private readonly eventosService: EventosService,
    private readonly temperaturasService: TemperaturasService,
  ) {}

  ngAfterViewInit(): void {
    this.mapa = L.map(this.mapaEl.nativeElement).setView(CENTRO_NEUTRO, ZOOM_INICIAL);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(this.mapa);

    this.mapa.on('zoomend', () => this.atualizarHeatmapParaZoom());
    this.legendaHeatmap = this.criarLegendaHeatmap();

    this.carregarEventos();
    this.carregarTemperaturas();
  }

  ngOnDestroy(): void {
    this.mapa?.remove();
  }

  /**
   * Camada de heatmap é independente da de eventos: se /temperaturas falhar ou
   * vier vazio, apenas desativamos o toggle — os marcadores de eventos não são
   * afetados.
   */
  private carregarTemperaturas(): void {
    this.temperaturasService.listar().subscribe({
      next: (pontos) => {
        if (!pontos || pontos.length === 0) {
          this.heatmapIndisponivel = true;
          return;
        }

        const dados: L.HeatLatLngTuple[] = pontos.map((ponto) => this.paraTuplaHeatmap(ponto));
        const { radius, blur } = this.calcularRadiusBlur(this.mapa?.getZoom() ?? ZOOM_INICIAL);
        this.heatLayer = L.heatLayer(dados, {
          radius,
          blur,
          max: 1.0,
          maxZoom: HEATMAP_MAX_ZOOM,
          // Opacidade real fica por conta do CSS no canvas gerado pelo plugin
          // (ver .leaflet-heatmap-layer no scss).
          gradient: GRADIENTE_HEATMAP,
        });

        this.atualizarHeatmapParaZoom();
      },
      error: () => {
        this.heatmapIndisponivel = true;
      },
    });
  }

  alternarHeatmap(): void {
    if (!this.mapa || !this.heatLayer) {
      return;
    }

    this.heatmapAtivo = !this.heatmapAtivo;
    this.atualizarHeatmapParaZoom();
  }

  /**
   * Fonte única de verdade pra visibilidade e radius/blur do heatmap: reage tanto
   * ao toggle do usuário quanto ao zoom atual. Acima de HEATMAP_ZOOM_LIMITE a
   * camada é removida (bolhas isoladas não ajudam ninguém) e os marcadores de
   * eventos seguem visíveis normalmente, sem depender deste método.
   */
  private atualizarHeatmapParaZoom(): void {
    if (!this.mapa || !this.heatLayer) {
      return;
    }

    const zoom = this.mapa.getZoom();
    const { radius, blur } = this.calcularRadiusBlur(zoom);
    this.heatLayer.setOptions({ radius, blur });

    const deveExibir = this.heatmapAtivo && zoom <= HEATMAP_ZOOM_LIMITE;
    const estaNoMapa = this.mapa.hasLayer(this.heatLayer);

    if (deveExibir && !estaNoMapa) {
      this.heatLayer.addTo(this.mapa);
      this.legendaHeatmap?.addTo(this.mapa);
    } else if (!deveExibir && estaNoMapa) {
      this.heatLayer.remove();
      this.legendaHeatmap?.remove();
    }
  }

  /**
   * Legenda customizada do heatmap: consome GRADIENTE_HEATMAP e a faixa de
   * temperatura fixa (TEMPERATURA_MINIMA/MAXIMA) diretamente, então nunca
   * dessincroniza das cores/paradas realmente usadas no L.heatLayer.
   */
  private criarLegendaHeatmap(): L.Control {
    const controle = new L.Control({ position: 'bottomright' });

    controle.onAdd = () => {
      const container = L.DomUtil.create('div', 'legenda-heatmap');
      L.DomEvent.disableClickPropagation(container);
      L.DomEvent.disableScrollPropagation(container);

      const titulo = L.DomUtil.create('div', 'legenda-heatmap__titulo', container);
      titulo.textContent = 'Temperatura (°C)';

      const paradas = Object.entries(GRADIENTE_HEATMAP)
        .map(([fracao, cor]) => ({ fracao: Number(fracao), cor }))
        .sort((a, b) => a.fracao - b.fracao);

      const barra = L.DomUtil.create('div', 'legenda-heatmap__barra', container);
      const cssStops = paradas.map((p) => `${p.cor} ${p.fracao * 100}%`).join(', ');
      barra.style.background = `linear-gradient(to right, ${cssStops})`;

      const faixas = L.DomUtil.create('div', 'legenda-heatmap__faixas', container);
      let fracaoAnterior = 0;
      paradas.forEach((parada, indice) => {
        const linha = L.DomUtil.create('div', 'legenda-heatmap__linha', faixas);

        const bolinha = L.DomUtil.create('span', 'legenda-heatmap__bolinha', linha);
        bolinha.style.background = parada.cor;

        const tempMin = Math.round(this.fracaoParaTemperatura(fracaoAnterior));
        const ehUltima = indice === paradas.length - 1;
        const texto = ehUltima
          ? `${tempMin}°C+`
          : `${tempMin}–${Math.round(this.fracaoParaTemperatura(parada.fracao))}°C`;

        const rotulo = L.DomUtil.create('span', 'legenda-heatmap__rotulo', linha);
        rotulo.textContent = texto;

        fracaoAnterior = parada.fracao;
      });

      return container;
    };

    return controle;
  }

  private fracaoParaTemperatura(fracao: number): number {
    return TEMPERATURA_MINIMA + fracao * (TEMPERATURA_MAXIMA - TEMPERATURA_MINIMA);
  }

  private calcularRadiusBlur(zoom: number): { radius: number; blur: number } {
    const zoomLimitado = Math.min(HEATMAP_ZOOM_LIMITE, Math.max(HEATMAP_ZOOM_RADIUS_MIN, zoom));
    const fracao =
      (zoomLimitado - HEATMAP_ZOOM_RADIUS_MIN) / (HEATMAP_ZOOM_LIMITE - HEATMAP_ZOOM_RADIUS_MIN);

    return {
      radius: HEATMAP_RADIUS_PAIS + (HEATMAP_RADIUS_CIDADE - HEATMAP_RADIUS_PAIS) * fracao,
      blur: HEATMAP_BLUR_PAIS + (HEATMAP_BLUR_CIDADE - HEATMAP_BLUR_PAIS) * fracao,
    };
  }

  private paraTuplaHeatmap(ponto: PontoTemperatura): L.HeatLatLngTuple {
    return [ponto.latitude, ponto.longitude, this.normalizarIntensidade(ponto.temperatura)];
  }

  private normalizarIntensidade(temperatura: number): number {
    const fracao =
      (temperatura - TEMPERATURA_MINIMA) / (TEMPERATURA_MAXIMA - TEMPERATURA_MINIMA);
    return Math.min(1, Math.max(0, fracao));
  }

  private carregarEventos(): void {
    this.eventosService.listar().subscribe({
      next: (colecao) => {
        this.carregando = false;
        const coordenadas = colecao.features.map((feature) => this.adicionarMarcador(feature));
        this.ajustarEnquadramento(coordenadas);
      },
      error: () => {
        this.carregando = false;
        this.erro =
          'Não foi possível carregar os eventos. Verifique se o backend está em execução em http://localhost:8000.';
      },
    });
  }

  /**
   * Enquadra o mapa nos marcadores carregados. Não depende de nenhum estado
   * específico — funciona igual se os eventos vierem só de RJ, só de SP, das
   * duas regiões ou de qualquer outra combinação futura.
   */
  private ajustarEnquadramento(coordenadas: L.LatLngExpression[]): void {
    if (!this.mapa || coordenadas.length === 0) {
      return;
    }

    if (coordenadas.length === 1) {
      this.mapa.setView(coordenadas[0], ZOOM_EVENTO_UNICO);
      return;
    }

    const bounds = L.latLngBounds(coordenadas);
    this.mapa.fitBounds(bounds, { padding: [50, 50] });
  }

  private adicionarMarcador(feature: EventoFeature): L.LatLngExpression {
    const [lng, lat] = feature.geometry.coordinates;
    const coordenada: L.LatLngExpression = [lat, lng];

    if (!this.mapa) {
      return coordenada;
    }

    const { tipo, severidade, municipio, estado, data_ocorrencia, descricao, url } = feature.properties;

    const cor = CORES_SEVERIDADE[severidade?.toLowerCase()] ?? COR_PADRAO;

    const marcador = L.circleMarker(coordenada, {
      radius: 8,
      color: cor,
      fillColor: cor,
      fillOpacity: 0.8,
      weight: 2,
    });

    marcador.bindPopup(this.montarPopup({ tipo, severidade, municipio, estado, data_ocorrencia, descricao, url }));
    marcador.addTo(this.mapa);

    return coordenada;
  }

  private montarPopup(props: {
    tipo: string;
    severidade: string;
    municipio: string;
    estado: string;
    data_ocorrencia: string;
    descricao: string;
    url: string;
  }): string {
    const descricaoResumida =
      props.descricao.length > 220 ? `${props.descricao.slice(0, 220)}…` : props.descricao;
    const linkSeguro = this.sanitizarUrl(props.url);

    return `
      <div class="popup-evento">
        <h3>${this.escapeHtml(this.capitalizar(props.tipo.replace(/_/g, ' ')))}</h3>
        <p><strong>Severidade:</strong> ${this.escapeHtml(this.capitalizar(props.severidade))}</p>
        <p><strong>Local:</strong> ${this.escapeHtml(props.municipio)} - ${this.escapeHtml(props.estado)}</p>
        <p><strong>Data:</strong> ${this.escapeHtml(this.formatarData(props.data_ocorrencia))}</p>
        <p>${this.escapeHtml(descricaoResumida)}</p>
        ${
          linkSeguro
            ? `<a href="${this.escapeHtml(linkSeguro)}" target="_blank" rel="noopener noreferrer">Ver fonte</a>`
            : ''
        }
      </div>
    `;
  }

  private formatarData(iso: string): string {
    const data = new Date(iso);
    if (Number.isNaN(data.getTime())) {
      return iso;
    }
    return data.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
  }

  private capitalizar(texto: string): string {
    if (!texto) {
      return texto;
    }
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  private sanitizarUrl(url: string): string | null {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null;
    } catch {
      return null;
    }
  }

  private escapeHtml(valor: string): string {
    const div = document.createElement('div');
    div.textContent = valor ?? '';
    return div.innerHTML;
  }
}
