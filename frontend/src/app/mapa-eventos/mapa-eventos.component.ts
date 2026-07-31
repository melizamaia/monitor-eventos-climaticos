import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import * as L from 'leaflet';
import { EventoFeature, EventosService } from '../services/eventos.service';

// Ponto médio aproximado entre RJ e SP — só usado como fallback enquanto os
// eventos carregam ou quando a coleção vier vazia; assim que houver marcadores,
// o mapa se ajusta automaticamente a eles (ver ajustarEnquadramento).
const CENTRO_NEUTRO: L.LatLngExpression = [-23.0, -44.5];
const ZOOM_INICIAL = 7;
const ZOOM_EVENTO_UNICO = 11;

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

  private mapa: L.Map | null = null;

  constructor(private readonly eventosService: EventosService) {}

  ngAfterViewInit(): void {
    this.mapa = L.map(this.mapaEl.nativeElement).setView(CENTRO_NEUTRO, ZOOM_INICIAL);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(this.mapa);

    this.carregarEventos();
  }

  ngOnDestroy(): void {
    this.mapa?.remove();
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
